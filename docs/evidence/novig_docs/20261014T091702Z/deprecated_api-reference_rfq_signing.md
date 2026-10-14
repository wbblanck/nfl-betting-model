> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Webhook Signing

> Verifying X-Novig-Signature on inbound RFQ webhooks

Every `/quote`, `/confirm`, and `/ping` call from Novig carries an `X-Novig-Signature` header. Verifying it on every request is how you confirm the call originated from Novig and that the body wasn't tampered with in transit.

## The scheme

```
X-Novig-Signature = BLAKE3_keyed_hash(shared_secret_bytes, raw_body_bytes).hex()
```

* **Algorithm:** BLAKE3 keyed hash.
* **Key:** the 32-byte secret you registered, decoded from its hex form.
* **Message:** the **raw bytes of the HTTP body**, exactly as received — before any JSON parse or normalization.
* **Output:** the 32-byte digest, hex-encoded as **64 lowercase characters**.

<Warning>
  Sign **bytes, not parsed JSON**. Any whitespace difference, key reordering, or re-serialization will change the digest and the
  signature won't match. Always read the raw body before parsing.
</Warning>

## Verifying

Use a BLAKE3 keyed-hash library and a constant-time comparison.

## What to do on a bad signature

Reject the request with `HTTP 401`. Don't process the body, don't echo it back, don't log the signature value. Returning anything in the 2xx range will cause Novig to treat your response as a valid quote/confirm.

## Sanity-checking your implementation

The quickest end-to-end check is [`POST /rfq/pricer/ping`](/deprecated/api-reference/rfq/registration): Novig sends a real signed request to your `/ping` handler and reports whether you accepted it, so you can confirm your verification works against a genuine Novig signature before any live quote flow.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.