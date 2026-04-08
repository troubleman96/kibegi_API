# Testing Guide for File Sharing System

Complete testing documentation with multiple methods to verify all endpoints work correctly.

## Quick Start

### Method 1: Automated Tests (Recommended)

Run the full test suite:

```bash
cd /home/troubleman/projects/Kibegi/Backend
python manage.py test sharing.tests -v 2
```

This will:
- ✅ Create test data automatically
- ✅ Test all 12 endpoints
- ✅ Verify permissions and validations
- ✅ Test error cases
- ✅ Show detailed output

**Expected Output:**
```
TEST 1: Share File - Success Case
✅ PASSED: File shared successfully

TEST 2: Share File - Not Owner (Should Fail)
✅ PASSED: Correctly prevented non-owner from sharing

... (12 tests total)

✅ ALL TESTS PASSED
```

---

### Method 2: Manual Test Script

Interactive test using your actual data:

```bash
cd /home/troubleman/projects/Kibegi/Backend
python sharing/manual_test.py
```

**You'll be prompted for:**
- Your email
- Your password

**The script will:**
- ✅ Login and get token
- ✅ Check your uploads and classes
- ✅ Test all endpoints with real data
- ✅ Show detailed responses
- ✅ Provide statistics

---

### Method 3: Swagger UI (Visual Testing)

1. **Open Swagger UI:**
   ```
   http://localhost:8000/api/schema/swagger-ui/
   ```

2. **Authenticate:**
   - Click "Authorize" button (top right)
   - Login at `/api/v1/auth/login/`
   - Copy the `access` token
   - Enter: `Bearer YOUR_ACCESS_TOKEN`
   - Click "Authorize"

3. **Test Endpoints:**
   Navigate to "File Sharing" section and test:
   
   #### POST /api/v1/sharing/ - Share a file
   ```json
   {
     "file_code": "ABC12345",
     "shared_with_id": 42,
     "message": "Check this out"
   }
   ```
   
   #### POST /api/v1/sharing/bulk/ - Bulk share
   ```json
   {
     "file_code": "ABC12345",
     "user_ids": [42, 43, 44],
     "message": "Study materials"
   }
   ```
   
   #### GET /api/v1/sharing/requests/ - List requests
   (No body needed)
   
   #### GET /api/v1/sharing/shared-with-me/ - List received
   Optional query: `?status=accepted`
   
   #### GET /api/v1/sharing/my-shares/ - List sent
   Optional query: `?status=pending`
   
   #### POST /api/v1/sharing/{share_id}/accept/ - Accept
   (No body, just share_id in URL)
   
   #### POST /api/v1/sharing/{share_id}/reject/ - Reject
   (No body, just share_id in URL)
   
   #### GET /api/v1/sharing/{share_id}/ - Get details
   (No body, just share_id in URL)

---

### Method 4: cURL Commands

Test from command line:

#### 1. Login First
```bash
# Login and save token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpassword"}' \
  | jq -r '.data.access')

echo "Token: $TOKEN"
```

#### 2. Share a File
```bash
curl -X POST http://localhost:8000/api/v1/sharing/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_code": "ABC12345",
    "shared_with_id": 42,
    "message": "Test share"
  }' | jq
```

#### 3. Bulk Share
```bash
curl -X POST http://localhost:8000/api/v1/sharing/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_code": "ABC12345",
    "user_ids": [42, 43],
    "message": "Bulk test"
  }' | jq
```

#### 4. List Pending Requests
```bash
curl -X GET http://localhost:8000/api/v1/sharing/requests/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 5. List Shared With Me
```bash
curl -X GET http://localhost:8000/api/v1/sharing/shared-with-me/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 6. List My Shares
```bash
curl -X GET http://localhost:8000/api/v1/sharing/my-shares/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 7. Accept Share
```bash
SHARE_ID="your-share-uuid-here"
curl -X POST http://localhost:8000/api/v1/sharing/$SHARE_ID/accept/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 8. Reject Share
```bash
SHARE_ID="your-share-uuid-here"
curl -X POST http://localhost:8000/api/v1/sharing/$SHARE_ID/reject/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## Test Coverage

### What Gets Tested

#### ✅ Endpoint Tests (12 tests)
1. Share file - success
2. Share file - not owner (fail)
3. Share file - duplicate (fail)
4. Bulk share
5. List pending requests
6. List shared with me
7. List my shares
8. Accept share
9. Reject share
10. Accept not recipient (fail)
11. Get share details
12. Unauthenticated access (fail)

#### ✅ Service Layer Tests (2 tests)
1. Permission checks
2. Share existence checks

#### ✅ What's Validated
- Authentication required
- Ownership permissions
- Duplicate prevention
- Class membership validation
- Status transitions
- Recipient-only actions
- Async processing (bulk)

---

## Troubleshooting

### Test Failures

#### "No users found"
Create test users:
```bash
python manage.py createsuperuser
```

#### "No uploads found"
Upload a file via:
- Swagger UI: http://localhost:8000/api/schema/swagger-ui/
- Or API: POST /api/v1/uploads/

#### "Not member of any class"
Create and join a class:
- POST /api/v1/classes/
- POST /api/v1/classes/{id}/join/

#### "Authentication failed"
Check your credentials:
```python
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.get(email='your@email.com')
>>> user.set_password('newpassword')
>>> user.save()
```

---

## Expected Results

### Successful Test Run

```
✅ TEST 1: Share File - Success (201 Created)
✅ TEST 2: Not Owner - Blocked (400 Bad Request)
✅ TEST 3: Duplicate - Blocked (400 Bad Request)
✅ TEST 4: Bulk Share - Accepted (202 Accepted)
✅ TEST 5: List Requests - OK (200 OK)
✅ TEST 6: List Shared - OK (200 OK)
✅ TEST 7: List My Shares - OK (200 OK)
✅ TEST 8: Accept Share - Success (200 OK)
✅ TEST 9: Reject Share - Success (200 OK)
✅ TEST 10: Not Recipient - Blocked (404 Not Found)
✅ TEST 11: Share Details - OK (200 OK)
✅ TEST 12: No Auth - Blocked (401 Unauthorized)

ALL TESTS PASSED ✅
```

---

## Performance Testing

Test async behavior:

```bash
# Time a bulk share with 50 users
time curl -X POST http://localhost:8000/api/v1/sharing/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_code": "ABC12345",
    "user_ids": [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,
                 21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
                 41,42,43,44,45,46,47,48,49,50],
    "message": "Performance test"
  }'
```

**Expected:** <200ms response (async processing)

---

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# .github/workflows/test.yml
name: Test Sharing System

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          python manage.py test sharing.tests --verbosity=2
```

---

## Next Steps

After confirming all tests pass:

1. ✅ Test with real users
2. ✅ Monitor performance in production
3. ✅ Set up notification integration
4. ✅ Add rate limiting for bulk shares
5. ✅ Implement share analytics

---

**Last Updated:** November 2024  
**Test Coverage:** 100% of endpoints  
**Status:** All tests passing ✅
