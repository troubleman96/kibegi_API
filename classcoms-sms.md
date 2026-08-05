**Overview**

- **Goal:** Describe how the Class Communications app and the centralized SMS app are structured and how they interact.
- **Scope:** Models, services, views/urls, request flows, accounting (credits), provider integration, and where to look in the codebase.

**ClassComms App (what it is and how it works)**

- **Purpose:** UI/API for class reps to collect contacts, register public signups, and send broadcast SMS messages to class members.
- **Key models:**  
  - **ClassContact / ClassBroadcast / ClassBroadcastDelivery / ClassCommsProfile / ClassCommsWallet:** represent contacts, broadcasts, per-broadcast delivery records, public registration settings, and a legacy per-class SMS wallet.
  - Files: models.py
- **Business logic:**  
  - `ClassCommsService`: contact upsert, build broadcast message, wallet/profile helpers, and dispatch broadcast logic. After refactor it delegates actual sending to `SmsService` and syncs legacy wallet balances. See services.py.
- **API surface (CRUD + actions):**  
  - Profile: read/patch (get/patch). See views.py.  
  - Wallet: read/patch (get/patch). No wallet delete. See views.py.  
  - Contacts: list/create, retrieve/update/delete (full CRUD including delete). See `ClassContactListCreateAPIView` and `ClassContactDetailAPIView` in views.py.  
  - Broadcasts: list/create and detail (inspect). There is no delete endpoint for broadcasts by default. See `ClassBroadcastListCreateAPIView` and `ClassBroadcastDetailAPIView` in views.py.  
  - Public endpoints: public info and public registration (to let people self-register contact details). See `PublicRegistrationInfoAPIView` and `PublicRegistrationAPIView` in views.py.
- **Permissions & flow:**  
  - Manager checks via `ClassCommsService.user_can_manage_class_comms` (creator, lecturer, or representative). Views call a permission mixin to deny unauthorized actions.  
  - Broadcast flow: build message -> check wallet active and balance -> for each contact either skip (insufficient credits), record pending (dry-run) or send (calls SMS provider via `SmsService`) -> decrement wallet / sync central account -> persist per-contact delivery record (`ClassBroadcastDelivery`) with provider ids/responses.
- **Tests & docs:** Tests live in tests.py and an internal README in README.md.

**SMS App (centralized SMS engine — how it works)**

- **Purpose:** Centralized, reusable SMS account, delivery, and accounting logic used by multiple apps (schedule, classcomms, etc.). Encapsulates provider integration, credits management, and delivery records.
- **Key models:**  
  - `SmsAccount`: Generic owner (GenericForeignKey) so any model (class, user, etc.) can own an account; fields include `phone_number`, `sender_id`, `balance_credits`, `provider_name`, UUID PK. See models.py.  
  - `SmsDelivery`: Generic `context` (GenericForeignKey) to link deliveries to an originating object; stores `sms_account`, `status`, `provider_response`, `provider_message_id`, `credits_used`, timestamps. See models.py.
- **Service API:**  
  - `SmsService` (in services.py) exposes core operations:  
    - `get_account_for_owner(owner)` — find or create central account for an owner.  
    - `build_message(subject, body, venue)` — helper to compose SMS body.  
    - `send_single(account, phone_number, message, context=None, dry_run=False, cost=1, client=None)` — atomic operation that:  
      - obtains a DB row lock (select_for_update) on the account, verifies balance, deducts credits, creates an `SmsDelivery` record, calls the provider client, records provider response and message id, updates delivery status and account balance in DB. The `client` parameter is injectable to allow tests to mock the provider.  
    - `send_bulk(owner, recipients, ...)` — convenience wrapper for sending many messages; internally calls `send_single`.
- **Provider integration & testability:**  
  - Provider client wrapper exists at sms.py (e.g., `AfricasTalkingSmsClient`). `SmsService.send_single` accepts an optional `client` so callers/tests can pass a fake client. The management commands and services often create or accept the client and pass it forward.
- **Admin / serializers / views / urls:**  
  - Admin config: admin.py  
  - Serializers for API: serializers.py  
  - Views and endpoints to inspect accounts and deliveries: views.py and urls.py
- **Settings & wiring:**  
  - `apps.sms` is added to INSTALLED_APPS and routes are included under the project URLs. See settings.py and urls.py.
- **Accounting guarantees:**  
  - Credits deduction is done inside a DB transaction with `select_for_update` to avoid double-spend race conditions. `send_single` either fully succeeds (credits deducted, delivery recorded as SENT) or rolls back on failure (so credits are not lost).
- **Compatibility with legacy wallets:**  
  - Existing code used per-app legacy wallet models (e.g., `ClassCommsWallet`, `ScheduleSmsAccount`). To avoid breaking behavior/tests during migration: callers (schedule, classcomms) mirror legacy balance into `SmsAccount` before sending and sync the central account balance back into the legacy wallet after send. See:  
    - services.py — shim and calls to `SmsService.send_single`.  
    - services.py — dispatch now uses `SmsService` and syncs legacy wallet.  
    - Management commands that used to directly import provider client were re-exported to keep tests patchable (e.g., send_schedule_sms_reminders.py).
- **Migrations & tests:**  
  - Initial migration added: 0001_initial.py  
  - Tests that exercise sending use a mocked `client` and assert that central `SmsAccount` balance is adjusted and `SmsDelivery` is created. Legacy tests expect legacy wallet balance to change — the shim keeps those assertions working during migration.

**Typical request/operation flows (practical examples)**

- Create a contact via the public registration link:
  - Request hits `PublicRegistrationAPIView` -> uses `ClassCommsService.upsert_contact` -> creates/updates `ClassContact`.
  - No SMS is sent in this flow; contact appears in contacts list.

- Send a class broadcast:
  - API: POST to broadcast endpoint -> view serializes and saves `ClassBroadcast`, calls `ClassCommsService.dispatch_broadcast`.
  - `dispatch_broadcast` composes message, iterates contacts, and for each contact calls `SmsService.send_single(...)` (after mirroring legacy wallet if needed).  
  - `SmsService.send_single` performs atomic balance check/deduction + provider send, creates `SmsDelivery`. After send the legacy `ClassCommsWallet` is synced from the `SmsAccount` (so legacy tests/consumers observe the updated balance). The view returns the persisted broadcast and the per-contact `ClassBroadcastDelivery` rows.

- Schedule reminders (existing flow now using `SmsService`):
  - Periodic management command builds a provider client (or accepts injected client in tests), calls schedule service -> schedule service mirrors legacy schedule wallet into central account -> calls `SmsService.send_single` for each reminder -> syncs `ScheduleSmsDeliveryLog` from returned `SmsDelivery` for backwards compatibility.

**Where to look in the code (quick links)**

- ClassComms core: services.py, views.py, models.py, serializers.py
- SMS core: models.py, services.py, views.py, serializers.py
- Provider wrapper: sms.py
- Integration points: services.py and services.py
- Settings + routes: settings.py and urls.py

**Next steps I can take (pick one)**

- Add a `DELETE` endpoint for broadcasts and wire tests.  
- Create a one-off data migration to copy legacy wallet rows into `SmsAccount` (to remove the compatibility shim later).  
- Run the full test suite and open a PR with the refactor and migration notes.

Which of these would you like me to do next?