# Class QR Code Integration

This API now exposes scan-to-join QR data for classes.

## What the backend returns

In `GET /api/v1/classes/{id}/` and class create responses, the payload includes:

- `join_qr_value` - the legacy plain class code
- `join_qr_payload` - a structured object for the frontend
- `join_qr_image` - a `data:image/png;base64,...` QR image

Example:

```json
{
  "join_qr_value": "ABC123",
  "join_qr_payload": {
    "type": "class_join",
    "class_code": "ABC123",
    "class_name": "Mathematics",
    "join_endpoint": "/api/v1/classes/join/"
  },
  "join_qr_image": "data:image/png;base64,iVBORw0KGgoAAA..."
}
```

## Recommended frontend behavior

Use the QR result in one of these ways:

1. If the scanner returns a JSON string, parse it and read `class_code`.
2. If the scanner returns plain text, treat it as the class code directly.
3. Prefill the join form with the code, or call the join endpoint immediately.

## Safe parser example

```ts
type ClassJoinQrPayload = {
  type?: string;
  class_code?: string;
  class_name?: string;
  join_endpoint?: string;
};

export function parseClassJoinQrResult(scannedText: string) {
  try {
    const parsed = JSON.parse(scannedText) as ClassJoinQrPayload;
    if (parsed && typeof parsed === 'object' && parsed.class_code) {
      return {
        classCode: parsed.class_code,
        className: parsed.class_name ?? null,
        joinEndpoint: parsed.join_endpoint ?? '/api/v1/classes/join/',
        raw: scannedText,
      };
    }
  } catch {
    // Not JSON, fall through to plain class code handling.
  }

  const classCode = scannedText.trim().toUpperCase();
  return {
    classCode,
    className: null,
    joinEndpoint: '/api/v1/classes/join/',
    raw: scannedText,
  };
}
```

## Prefill the join form

```ts
const result = parseClassJoinQrResult(scannedText);
setJoinCode(result.classCode);
```

## Call the join endpoint directly

```ts
await api.post('/api/v1/classes/join/', {
  class_code: result.classCode,
});
```

## Render the QR image

If you want to show the QR image returned by the API:

```tsx
<img
  src={classData.join_qr_image}
  alt={`Join QR for ${classData.name}`}
/>
```

## Notes

- Keep `join_qr_value` for backward compatibility.
- Prefer `join_qr_payload` for new frontend code.
- The QR image itself encodes the JSON payload, so scanners that return raw text will still work if the frontend parses JSON first.
