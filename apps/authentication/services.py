import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger('kibegi')


def _year():
    import datetime
    return datetime.date.today().year


class EmailService:
    PRIMARY      = "#0F172A"   # slate-900  — brand dark
    ACCENT       = "#06B6D4"   # cyan-500   — highlight
    ACCENT_LIGHT = "#ECFEFF"   # cyan-50
    ACCENT_DARK  = "#0891B2"   # cyan-600
    TEXT         = "#1E293B"   # slate-800
    MUTED        = "#64748B"   # slate-500
    BORDER       = "#E2E8F0"   # slate-200
    BG           = "#F8FAFC"   # slate-50
    WHITE        = "#FFFFFF"
    WARN_BG      = "#FFFBEB"
    WARN_BORDER  = "#FDE68A"
    WARN_TEXT    = "#92400E"
    SUCCESS_BG   = "#F0FDF4"
    SUCCESS_TEXT = "#166534"
    DANGER_BG    = "#FEF2F2"
    DANGER_TEXT  = "#991B1B"

    # ── base template ────────────────────────────────────────────────────────

    @staticmethod
    def _base(content: str, preview: str = "") -> str:
        y = _year()
        P = EmailService.PRIMARY
        A = EmailService.ACCENT
        AD = EmailService.ACCENT_DARK
        AL = EmailService.ACCENT_LIGHT
        T = EmailService.TEXT
        M = EmailService.MUTED
        B = EmailService.BORDER
        BG = EmailService.BG
        W = EmailService.WHITE

        return f'''<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Kibegi</title>
  <style>
    body,table,td,p,a {{margin:0;padding:0;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;}}
    table,td {{mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;}}
    body {{background-color:{BG};font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}}
    @media only screen and (max-width:620px){{
      .wrap{{width:100%!important;padding:16px!important;}}
      .otp{{font-size:30px!important;letter-spacing:10px!important;}}
    }}
  </style>
</head>
<body>
  <!-- preview text -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
    {preview}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" class="wrap" width="560" cellpadding="0" cellspacing="0"
             style="background:{W};border-radius:12px;border:1px solid {B};overflow:hidden;">

        <!-- ── header ── -->
        <tr>
          <td style="background:{P};padding:28px 40px;text-align:center;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr><td align="center">
                <!-- wordmark -->
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="background:{A};border-radius:6px;padding:5px 10px;vertical-align:middle;">
                      <span style="font-size:14px;font-weight:700;color:{P};letter-spacing:0.5px;font-family:Georgia,serif;">K</span>
                    </td>
                    <td style="padding-left:10px;vertical-align:middle;">
                      <span style="font-size:22px;font-weight:700;color:{W};letter-spacing:0.3px;font-family:Georgia,serif;">Kibegi</span>
                    </td>
                  </tr>
                </table>
              </td></tr>
            </table>
          </td>
        </tr>

        <!-- ── body ── -->
        {content}

        <!-- ── footer ── -->
        <tr>
          <td style="background:{BG};border-top:1px solid {B};padding:24px 40px;text-align:center;">
            <p style="margin:0 0 6px 0;font-size:13px;color:{M};line-height:1.6;">
              This is an automated message — please do not reply directly to this email.
            </p>
            <p style="margin:0;font-size:12px;color:{M};">
              &copy; {y} Kibegi &nbsp;·&nbsp; All rights reserved
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>'''

    # ── OTP content block ─────────────────────────────────────────────────────

    @staticmethod
    def _otp_block(user_name: str, otp_code: str, expiry_minutes: int,
                   purpose: str = "registration", extra_msg: str = "") -> str:
        A = EmailService.ACCENT
        AD = EmailService.ACCENT_DARK
        AL = EmailService.ACCENT_LIGHT
        T = EmailService.TEXT
        M = EmailService.MUTED
        WB = EmailService.WARN_BG
        WBD = EmailService.WARN_BORDER
        WT = EmailService.WARN_TEXT

        if purpose == "registration":
            badge = "Account Verification"
            headline = "Verify your email address"
            body_line = (
                f"You're almost there! Enter the code below in the Kibegi sign-up screen "
                f"to activate your account."
            )
            outro = "Once verified, you'll have full access to classes, materials, and collaboration tools on Kibegi."
        elif purpose == "password_reset":
            badge = "Password Reset"
            headline = "Reset your password"
            body_line = "We received a request to reset your Kibegi password. Use the code below to continue."
            outro = "After verification you can set a new password. If you didn't request this, no action is needed."
        else:
            badge = "Verification"
            headline = "Your verification code"
            body_line = "Use the code below to complete your request on Kibegi."
            outro = ""

        extra = f'<p style="margin:16px 0 0 0;font-size:14px;color:{M};text-align:center;">{extra_msg}</p>' if extra_msg else ""

        return f'''
        <tr>
          <td style="padding:36px 40px 0 40px;text-align:center;">
            <!-- badge -->
            <span style="display:inline-block;background:{AL};color:{AD};font-size:11px;font-weight:700;
                         letter-spacing:0.8px;text-transform:uppercase;padding:4px 12px;border-radius:20px;
                         border:1px solid {A};">
              {badge}
            </span>

            <!-- headline -->
            <h1 style="margin:20px 0 10px 0;font-size:22px;font-weight:700;color:{T};line-height:1.3;">
              {headline}
            </h1>

            <!-- greeting -->
            <p style="margin:0 0 18px 0;font-size:15px;color:{M};">
              Hi <strong style="color:{T};">{user_name}</strong>,
            </p>

            <!-- body -->
            <p style="margin:0 0 28px 0;font-size:15px;color:{M};line-height:1.7;max-width:420px;margin-left:auto;margin-right:auto;">
              {body_line}
            </p>
          </td>
        </tr>

        <!-- OTP box -->
        <tr>
          <td style="padding:0 40px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr><td align="center">
                <div style="display:inline-block;background:{AL};border:2px solid {A};border-radius:10px;padding:20px 48px;">
                  <span class="otp" style="font-size:38px;font-weight:800;letter-spacing:14px;
                               color:{AD};font-family:'Courier New',Courier,monospace;display:block;">
                    {otp_code}
                  </span>
                  <p style="margin:8px 0 0 0;font-size:12px;color:{M};text-align:center;letter-spacing:0;">
                    Expires in <strong>{expiry_minutes} minutes</strong>
                  </p>
                </div>
              </td></tr>
            </table>
          </td>
        </tr>

        <!-- security notice -->
        <tr>
          <td style="padding:24px 40px 8px 40px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="background:{WB};border:1px solid {WBD};border-radius:8px;">
              <tr><td style="padding:16px 20px;">
                <p style="margin:0 0 8px 0;font-size:13px;font-weight:700;color:{WT};">Security notice</p>
                <ul style="margin:0;padding-left:18px;font-size:13px;color:{WT};line-height:1.9;">
                  <li>Never share this code — Kibegi will never ask for it</li>
                  <li>If you didn't request this, you can safely ignore this email</li>
                </ul>
              </td></tr>
            </table>
          </td>
        </tr>

        <!-- outro -->
        <tr>
          <td style="padding:20px 40px 32px 40px;text-align:center;">
            <p style="margin:0;font-size:14px;color:{M};line-height:1.7;">{outro}</p>
            {extra}
          </td>
        </tr>
'''

    # ── public send methods ───────────────────────────────────────────────────

    @classmethod
    def send_registration_otp(cls, email: str, user_name: str,
                               otp_code: str, expiry_minutes: int = 10) -> bool:
        subject = f"Kibegi — Your verification code: {otp_code}"
        preview = f"Your Kibegi verification code is {otp_code}. It expires in {expiry_minutes} minutes."
        content = cls._otp_block(user_name, otp_code, expiry_minutes, purpose="registration")
        html = cls._base(content, preview)
        plain = (
            f"Hi {user_name},\n\n"
            f"Your Kibegi verification code is: {otp_code}\n\n"
            f"This code expires in {expiry_minutes} minutes.\n\n"
            f"Do not share this code with anyone.\n"
            f"If you didn't sign up, you can ignore this email.\n\n"
            f"— The Kibegi Team\n"
            f"© {_year()} Kibegi"
        )
        return cls._send(email, subject, plain, html)

    @classmethod
    def send_password_reset_otp(cls, email: str, user_name: str,
                                 otp_code: str, expiry_minutes: int = 10) -> bool:
        subject = f"Kibegi — Password reset code: {otp_code}"
        preview = f"Your Kibegi password reset code is {otp_code}. Expires in {expiry_minutes} minutes."
        content = cls._otp_block(user_name, otp_code, expiry_minutes, purpose="password_reset")
        html = cls._base(content, preview)
        plain = (
            f"Hi {user_name},\n\n"
            f"Your Kibegi password reset code is: {otp_code}\n\n"
            f"This code expires in {expiry_minutes} minutes.\n\n"
            f"Do not share this code. If you didn't request a reset, ignore this email.\n\n"
            f"— The Kibegi Team\n"
            f"© {_year()} Kibegi"
        )
        return cls._send(email, subject, plain, html)

    @classmethod
    def send_resend_otp(cls, email: str, user_name: str, otp_code: str,
                         expiry_minutes: int = 10, purpose: str = "registration") -> bool:
        if purpose == "registration":
            subject = f"Kibegi — New verification code: {otp_code}"
            preview = f"Your new Kibegi verification code is {otp_code}."
        else:
            subject = f"Kibegi — New password reset code: {otp_code}"
            preview = f"Your new Kibegi password reset code is {otp_code}."
        content = cls._otp_block(user_name, otp_code, expiry_minutes, purpose=purpose,
                                  extra_msg="Your previous code has been invalidated.")
        html = cls._base(content, preview)
        action = "verification" if purpose == "registration" else "password reset"
        plain = (
            f"Hi {user_name},\n\n"
            f"Your new Kibegi {action} code is: {otp_code}\n\n"
            f"Expires in {expiry_minutes} minutes. Your previous code has been invalidated.\n\n"
            f"— The Kibegi Team\n"
            f"© {_year()} Kibegi"
        )
        return cls._send(email, subject, plain, html)

    @classmethod
    def send_lecturer_approved(cls, email: str, user_name: str) -> bool:
        subject = "Kibegi — Your lecturer account is approved"
        preview = "Your Kibegi lecturer account is now active."
        SB = cls.SUCCESS_BG
        ST = cls.SUCCESS_TEXT
        A = cls.ACCENT
        AD = cls.ACCENT_DARK
        AL = cls.ACCENT_LIGHT
        T = cls.TEXT
        M = cls.MUTED
        content = f'''
        <tr>
          <td style="padding:36px 40px 32px 40px;text-align:center;">
            <span style="display:inline-block;background:{AL};color:{AD};font-size:11px;font-weight:700;
                         letter-spacing:0.8px;text-transform:uppercase;padding:4px 12px;border-radius:20px;
                         border:1px solid {A};">Account Update</span>
            <h1 style="margin:20px 0 10px 0;font-size:22px;font-weight:700;color:{T};">Your account is approved!</h1>
            <p style="margin:0 0 20px 0;font-size:15px;color:{M};">Hi <strong style="color:{T};">{user_name}</strong>,</p>
            <p style="margin:0 0 24px 0;font-size:15px;color:{M};line-height:1.7;max-width:400px;margin-left:auto;margin-right:auto;">
              Great news — your Kibegi lecturer account has been reviewed and approved by our team.
              You can now log in and start creating classes, sharing materials, and collaborating with students.
            </p>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="background:{SB};border:1px solid #86EFAC;border-radius:8px;max-width:400px;margin:0 auto;">
              <tr><td style="padding:16px 20px;text-align:center;">
                <p style="margin:0;font-size:14px;font-weight:600;color:{ST};">
                  ✓ &nbsp;Your account is now active. Log in to get started.
                </p>
              </td></tr>
            </table>
          </td>
        </tr>'''
        html = cls._base(content, preview)
        plain = (
            f"Hi {user_name},\n\n"
            f"Your Kibegi lecturer account has been approved. You can now log in.\n\n"
            f"— The Kibegi Team\n"
            f"© {_year()} Kibegi"
        )
        return cls._send(email, subject, plain, html)

    @classmethod
    def send_lecturer_rejected(cls, email: str, user_name: str) -> bool:
        subject = "Kibegi — Lecturer account application update"
        preview = "An update regarding your Kibegi lecturer account application."
        T = cls.TEXT
        M = cls.MUTED
        A = cls.ACCENT
        AD = cls.ACCENT_DARK
        AL = cls.ACCENT_LIGHT
        DB = cls.DANGER_BG
        DT = cls.DANGER_TEXT
        content = f'''
        <tr>
          <td style="padding:36px 40px 32px 40px;text-align:center;">
            <span style="display:inline-block;background:{AL};color:{AD};font-size:11px;font-weight:700;
                         letter-spacing:0.8px;text-transform:uppercase;padding:4px 12px;border-radius:20px;
                         border:1px solid {A};">Account Update</span>
            <h1 style="margin:20px 0 10px 0;font-size:22px;font-weight:700;color:{T};">Application not approved</h1>
            <p style="margin:0 0 20px 0;font-size:15px;color:{M};">Hi <strong style="color:{T};">{user_name}</strong>,</p>
            <p style="margin:0 0 24px 0;font-size:15px;color:{M};line-height:1.7;max-width:400px;margin-left:auto;margin-right:auto;">
              After reviewing your lecturer account application, we were unable to approve it at this time.
              If you believe this is a mistake, please contact our support team and we'll be happy to assist.
            </p>
          </td>
        </tr>'''
        html = cls._base(content, preview)
        plain = (
            f"Hi {user_name},\n\n"
            f"Your Kibegi lecturer account application was not approved.\n"
            f"Contact our support team if you need assistance.\n\n"
            f"— The Kibegi Team\n"
            f"© {_year()} Kibegi"
        )
        return cls._send(email, subject, plain, html)

    # ── internal ──────────────────────────────────────────────────────────────

    @classmethod
    def _send(cls, to: str, subject: str, plain: str, html: str) -> bool:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not from_email:
            logger.warning("DEFAULT_FROM_EMAIL not configured. Cannot send email.")
            return False
        try:
            msg = EmailMultiAlternatives(subject=subject, body=plain,
                                         from_email=from_email, to=[to])
            msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=False)
            logger.info("Email sent to %s", to)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", to, exc)
            return False
