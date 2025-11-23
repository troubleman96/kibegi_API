# 🚀 QUICK TEST GUIDE

## Run Tests Now (Choose One Method)

### ⚡ Method 1: Automated Tests (Fastest)
```bash
cd /home/troubleman/projects/Kibegi/Backend
source venv/bin/activate
python manage.py test sharing.tests -v 2
```

### 📱 Method 2: Manual Testing with Your Data
```bash
cd /home/troubleman/projects/Kibegi/Backend
python sharing/manual_test.py
```
You'll be prompted for email/password.

### 🌐 Method 3: Swagger UI (Visual)
1. Open: http://localhost:8000/api/schema/swagger-ui/
2. Login at `/api/v1/auth/login/`
3. Click "Authorize" → Enter `Bearer YOUR_TOKEN`
4. Test endpoints in "File Sharing" section

### 💻 Method 4: Quick cURL Test
```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"YOUR_EMAIL","password":"YOUR_PASSWORD"}' \
  | grep -o '"access":"[^"]*' | cut -d'"' -f4)

# 2. Share a file
curl -X POST http://localhost:8000/api/v1/sharing/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_code":"ABC12345","shared_with_id":2,"message":"Test"}'

# 3. List my shares
curl -X GET http://localhost:8000/api/v1/sharing/my-shares/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📋 All Endpoints to Test

| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/api/v1/sharing/` | Share file with one user |
| POST | `/api/v1/sharing/bulk/` | Share with multiple users |
| GET | `/api/v1/sharing/requests/` | List pending requests |
| GET | `/api/v1/sharing/shared-with-me/` | List received shares |
| GET | `/api/v1/sharing/my-shares/` | List sent shares |
| POST | `/api/v1/sharing/{id}/accept/` | Accept a share |
| POST | `/api/v1/sharing/{id}/reject/` | Reject a share |
| GET | `/api/v1/sharing/{id}/` | Get share details |

---

## ✅ What Success Looks Like

### Share File (201 Created)
```json
{
  "success": true,
  "message": "File shared successfully",
  "data": {
    "id": "uuid-here",
    "status": "pending",
    "shared_by_name": "John Doe"
  }
}
```

### Bulk Share (202 Accepted)
```json
{
  "success": true,
  "message": "Sharing with 3 users in progress",
  "data": {
    "status": "processing",
    "user_count": 3
  }
}
```

### List Operations (200 OK)
```json
{
  "success": true,
  "data": {
    "count": 5,
    "results": [...]
  }
}
```

---

## 🐛 Common Issues

### "Authentication credentials not provided"
→ Add token: `-H "Authorization: Bearer YOUR_TOKEN"`

### "File not found"
→ Check file_code: `GET /api/v1/uploads/`

### "User not found"
→ Use correct user ID (integer, not UUID)

### "Not in same class"
→ Both users must be members of the file's class

### "This is not your file"
→ Only file owner can share

---

## 🎯 Quick Smoke Test (30 seconds)

```bash
# 1. Start server (if not running)
python manage.py runserver

# 2. Open another terminal and run:
cd /home/troubleman/projects/Kibegi/Backend
python sharing/manual_test.py

# 3. Check output - should see ✅ for each test
```

---

## 📊 Check Database

```bash
python manage.py shell
```

```python
from sharing.models import SharedFile

# Count shares
print(f"Total shares: {SharedFile.objects.count()}")
print(f"Pending: {SharedFile.objects.filter(status='pending').count()}")
print(f"Accepted: {SharedFile.objects.filter(status='accepted').count()}")

# Recent shares
for share in SharedFile.objects.order_by('-shared_at')[:5]:
    print(f"{share.shared_by.full_name} → {share.shared_with.full_name}: {share.status}")
```

---

## 🔥 Ultra Quick Test (One Command)

```bash
# Run all tests and show summary
cd /home/troubleman/projects/Kibegi/Backend && \
source venv/bin/activate && \
python manage.py test sharing.tests -v 0 && \
echo "✅ ALL TESTS PASSED!"
```

---

**Need help?** Check `sharing/TESTING.md` for detailed docs.
