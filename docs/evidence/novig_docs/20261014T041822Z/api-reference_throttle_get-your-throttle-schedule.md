> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get your throttle schedule

> | | |
| --- | --- |
| **Key** | `any` |
| **Throttle** | `free` |
| **Cost** | `0 /request` |
| **Answers** | <span class="st st-ok">200</span> <span class="st st-warn">401</span> <span class="st st-warn">403</span> <span class="st st-hold">423</span> <span class="st st-hold">429</span> <span class="st st-warn">451</span> |
| **Idempotent** | `true` |



## OpenAPI

````yaml /api-reference/spec-files/openapi-v3.json get /v3/limits
openapi: 3.1.0
info:
  contact:
    email: tech@novig.com
    name: Contact
    url: https://novig.com
  description: >-
    Place orders over signed REST. Watch the book and your fills on one
    websocket.
  title: Novig API
  version: 3.0.0
servers:
  - description: Paper
    url: https://api.paper.novig.com
security: []
tags:
  - description: >-
      The tradable world: events, markets and outcomes, and the vocabularies
      their fields use.
    name: Catalog
  - description: >-
      Markets and events that are no longer in the catalog, and the caller's
      positions. These records have no age limit.
    name: History
  - description: 'Signature debugging: the string the server built from your request.'
    name: Authentication
  - description: Subaccounts and their ledgers.
    name: Accounts
  - description: Orders, and the caller's own trading state.
    name: Execution
  - description: The websocket entry point.
    name: Streaming
  - description: The rate-limit schedule, read at runtime.
    name: Throttle
paths:
  /v3/limits:
    get:
      tags:
        - Throttle
      summary: Get your throttle schedule
      description: >-
        | | |

        | --- | --- |

        | **Key** | `any` |

        | **Throttle** | `free` |

        | **Cost** | `0 /request` |

        | **Answers** | <span class="st st-ok">200</span> <span class="st
        st-warn">401</span> <span class="st st-warn">403</span> <span class="st
        st-hold">423</span> <span class="st st-hold">429</span> <span class="st
        st-warn">451</span> |

        | **Idempotent** | `true` |
      operationId: getLimits
      responses:
        '200':
          content:
            application/json:
              example:
                account:
                  capacity: 64
                  refillPerSec: 8
                cancel:
                  capacity: 256
                  refillPerSec: 16
                history:
                  capacity: 512
                  refillPerSec: 4
                maxWatchedMarkets: 8192
                place:
                  capacity: 256
                  refillPerSec: 8
                read:
                  capacity: 64
                  refillPerSec: 16
                stream:
                  capacity: 512
                  refillPerSec: 32
              schema:
                $ref: '#/components/schemas/LimitsResponse'
          description: Your schedule.
        '401':
          content:
            application/json:
              example:
                code: SIGNATURE_REJECTED
                message: signature verification failed
              schema:
                $ref: '#/components/schemas/ErrorBody'
          description: >-
            The signature is absent or invalid, or the key is unknown, revoked,
            or expired.
        '403':
          content:
            application/json:
              example:
                code: SCOPE_INSUFFICIENT
                message: api key scope is insufficient for this route
              schema:
                $ref: '#/components/schemas/ErrorBody'
          description: The key's scope does not grant this route.
        '423':
          content:
            application/json:
              example:
                code: ACCOUNT_LOCKED
                message: The account is locked out of trading.
              schema:
                $ref: '#/components/schemas/ErrorBody'
          description: The account is locked out of trading.
        '429':
          content:
            application/json:
              example:
                code: RATE_LIMIT_EXCEEDED
                message: Rate limit exceeded. Please wait before retrying.
              schema:
                $ref: '#/components/schemas/ErrorBody'
          description: >-
            The throttle is empty. Wait the number of seconds in `Retry-After`.
            Then retry.
        '451':
          content:
            application/json:
              example:
                code: ANONYMIZED_NETWORK
                message: The request came over a VPN, a proxy, or a Tor exit.
              schema:
                $ref: '#/components/schemas/ErrorBody'
          description: >-
            Geolocation refused the request: an anonymized network, a restricted
            region, or, for a placement, no device geolocation in the last 3
            days.
      security:
        - keyId: []
          signature: []
          timestamp: []
      x-codeSamples:
        - lang: bash
          source: |
            HOST=https://api.paper.novig.com
            KEY_ID=2c9a7e1d-5b3f-4e8a-a6d0-9f1b3c5e7a24
            PEM=novig-api-key-mgmt-1.pem

            REQ_PATH="/v3/limits"
            QUERY=""
            BODY=''
            TS=$(date +%s000)
            HASH=$(printf %s "$BODY" \
              | openssl dgst -sha256 -r | cut -d" " -f1)

            # openssl signs a file, not a pipe. base64 -A never wraps.
            printf 'NOVIG-V3\n%s\nGET\n%s\n%s\n%s' \
              "$TS" "$REQ_PATH" "$QUERY" "$HASH" > canon.bin
            SIG=$(openssl pkeyutl -sign -rawin -inkey "$PEM" \
              -in canon.bin | openssl base64 -A)

            curl -s -X GET "$HOST$REQ_PATH${QUERY:+?$QUERY}" \
              -H "Novig-Key-Id: $KEY_ID" \
              -H "Novig-Timestamp: $TS" \
              -H "Novig-Signature: $SIG"
        - lang: rust
          source: |
            use base64::prelude::*;
            use ed25519_dalek::pkcs8::DecodePrivateKey;
            use ed25519_dalek::{Signer, SigningKey};
            use reqwest::blocking::{Client, Request};
            use reqwest::{Method, Url};
            use sha2::{Digest, Sha256};
            use std::time::{SystemTime, UNIX_EPOCH};

            const HOST: &str = "https://api.paper.novig.com";
            const KEY_ID: &str =
                "2c9a7e1d-5b3f-4e8a-a6d0-9f1b3c5e7a24";
            const PEM: &str = "novig-api-key-mgmt-1.pem";

            fn main() -> anyhow::Result<()> {
                let key = Key::load(KEY_ID, PEM)?;
                let client = Client::new();
                let path = "/v3/limits";
                let url = format!("{HOST}{path}");
                let req = client
                    .get(url)
                    .build()?
                    .sign(&key)?;
                println!("{}", client.execute(req)?.text()?);
                Ok(())
            }

            /// An API key: the id the server looks up, and the
            /// private half that signs.
            struct Key {
                id: &'static str,
                signer: SigningKey,
            }

            impl Key {
                fn load(id: &'static str, pem: &str) -> anyhow::Result<Self> {
                    let signer =
                        SigningKey::read_pkcs8_pem_file(pem)?;
                    Ok(Self { id, signer })
                }
            }

            /// Signs a built request over the method, path, query and
            /// body it will send, so the two can never disagree.
            trait Sign: Sized {
                fn sign(self, key: &Key) -> anyhow::Result<Self>;
            }

            impl Sign for Request {
                fn sign(mut self, key: &Key) -> anyhow::Result<Self> {
                    let ts = SystemTime::now()
                        .duration_since(UNIX_EPOCH)?
                        .as_millis()
                        .to_string();
                    let body = self.body().and_then(|b| b.as_bytes());
                    let body = body.unwrap_or_default();
                    let canon = Canonical::new(
                        &ts,
                        self.method(),
                        self.url(),
                        body,
                    );
                    let sig = key.signer.sign(canon.0.as_bytes());
                    let sig = BASE64_STANDARD.encode(sig.to_bytes());
                    let headers = self.headers_mut();
                    headers.insert("Novig-Key-Id", key.id.parse()?);
                    headers.insert("Novig-Timestamp", ts.parse()?);
                    headers.insert("Novig-Signature", sig.parse()?);
                    Ok(self)
                }
            }

            /// The six NOVIG-V3 lines, joined by LF.
            struct Canonical(String);

            impl Canonical {
                fn new(
                    ts: &str,
                    method: &Method,
                    url: &Url,
                    body: &[u8],
                ) -> Self {
                    let query =
                        Query::from(url.query().unwrap_or(""));
                    let hash = format!("{:x}", Sha256::digest(body));
                    let method = method.as_str();
                    let path = url.path();
                    let lines = [
                        "NOVIG-V3", ts, method, path, &query.0, &hash,
                    ];
                    Self(lines.join("\n"))
                }
            }

            /// Each part decoded and re-encoded, then sorted by
            /// name and value.
            struct Query(String);

            impl From<&str> for Query {
                fn from(raw: &str) -> Self {
                    let mut pairs = raw
                        .split('&')
                        .filter(|pair| !pair.is_empty())
                        .map(|pair| {
                            pair.split_once('=').unwrap_or((pair, ""))
                        })
                        .map(|(k, v)| {
                            (Self::encode(k), Self::encode(v))
                        })
                        .collect::<Vec<_>>();
                    pairs.sort();
                    let pairs =
                        pairs.iter().map(|(k, v)| format!("{k}={v}"));
                    Self(pairs.collect::<Vec<_>>().join("&"))
                }
            }

            impl Query {
                fn encode(part: &str) -> String {
                    Self::decode(part)
                        .iter()
                        .map(|&b| match b {
                            b'-' | b'.' | b'_' | b'~' => {
                                (b as char).to_string()
                            }
                            _ if b.is_ascii_alphanumeric() => {
                                (b as char).to_string()
                            }
                            _ => format!("%{b:02X}"),
                        })
                        .collect()
                }

                /// Only `%XX` decodes. A bare `+` stays a `+`.
                fn decode(part: &str) -> Vec<u8> {
                    let raw = part.as_bytes();
                    let mut out = Vec::with_capacity(raw.len());
                    let mut i = 0;
                    while i < raw.len() {
                        let escape =
                            raw.get(i + 1..i + 3).and_then(Self::hex);
                        match (raw[i], escape) {
                            (b'%', Some(byte)) => {
                                out.push(byte);
                                i += 3;
                            }
                            (byte, _) => {
                                out.push(byte);
                                i += 1;
                            }
                        }
                    }
                    out
                }

                fn hex(pair: &[u8]) -> Option<u8> {
                    let hi = (pair[0] as char).to_digit(16)?;
                    let lo = (pair[1] as char).to_digit(16)?;
                    Some((hi * 16 + lo) as u8)
                }
            }
        - lang: python
          source: |
            import base64, hashlib, time, urllib.request
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key)

            HOST = "https://api.paper.novig.com"
            KEY_ID = "2c9a7e1d-5b3f-4e8a-a6d0-9f1b3c5e7a24"
            PEM = "novig-api-key-mgmt-1.pem"

            path = "/v3/limits"
            query = ""
            body = b""

            ts = str(int(time.time() * 1000))
            canon = "\n".join(["NOVIG-V3", ts, "GET", path, query,
                               hashlib.sha256(body).hexdigest()])
            key = load_pem_private_key(open(PEM, "rb").read(), None)
            headers = {
                "Novig-Key-Id": KEY_ID,
                "Novig-Timestamp": ts,
                "Novig-Signature": base64.b64encode(
                    key.sign(canon.encode())).decode(),
            }
            url = f"{HOST}{path}"
            req = urllib.request.Request(
                url, data=body or None,
                method="GET", headers=headers)
            print(urllib.request.urlopen(req).read().decode())
        - lang: typescript
          source: |
            import {
              createHash, createPrivateKey, sign,
            } from "node:crypto";
            import { readFileSync } from "node:fs";

            const HOST = "https://api.paper.novig.com";
            const KEY_ID = "2c9a7e1d-5b3f-4e8a-a6d0-9f1b3c5e7a24";
            const PEM = "novig-api-key-mgmt-1.pem";

            const path = "/v3/limits";
            const query = "";
            const body = "";

            const ts = Date.now().toString();
            const hash =
              createHash("sha256").update(body).digest("hex");
            const canon = [
              "NOVIG-V3", ts, "GET", path, query, hash,
            ].join("\n");
            const key = createPrivateKey(readFileSync(PEM));
            const headers: Record<string, string> = {
              "Novig-Key-Id": KEY_ID,
              "Novig-Timestamp": ts,
              "Novig-Signature": sign(null, Buffer.from(canon), key)
                .toString("base64"),
            };
            const url = `${HOST}${path}`;
            const r = await fetch(url, {
              method: "GET",
              headers,
            });
            console.log(await r.text());
components:
  schemas:
    LimitsResponse:
      description: |-
        The rate-limit schedule: one `BucketLimit` per bucket. The schedule is
        static.
      properties:
        account:
          $ref: '#/components/schemas/BucketLimit'
          description: 'The bucket for private reads: orders, positions, and account data.'
        cancel:
          $ref: '#/components/schemas/BucketLimit'
          description: The bucket for canceling orders. Its limits are never below `place`.
        history:
          $ref: '#/components/schemas/BucketLimit'
          description: >-
            The bucket for database-backed record reads: fills, transactions,
            and

            settled orders. Each read costs a base plus one token per page of
            rows.
        maxWatchedMarkets:
          description: >-
            The most markets one websocket connection may watch at once. An
            event

            counts as the markets it contains.
          format: int32
          minimum: 0
          type: integer
        place:
          $ref: '#/components/schemas/BucketLimit'
          description: The bucket for placing orders. A batch costs one token per order.
        read:
          $ref: '#/components/schemas/BucketLimit'
          description: >-
            The bucket for public reads: catalog, books, stats, and archive
            pages.
        stream:
          $ref: '#/components/schemas/BucketLimit'
          description: |-
            The bucket for websocket requests: subscribe, unsubscribe, snapshot,
            and status.
      required:
        - read
        - account
        - place
        - cancel
        - stream
        - history
        - maxWatchedMarkets
      type: object
    ErrorBody:
      description: Every error on the surface carries this body.
      properties:
        code:
          description: Stable identifier. The only field to branch on.
          example: MARKET_NOT_FOUND
          type: string
        message:
          description: Human-readable. Not stable. Never match on it.
          type: string
        nonce:
          description: The websocket request that failed. Absent on REST.
          format: int64
          maximum: 9007199254740991
          minimum: 0
          type:
            - integer
            - 'null'
        rejected:
          description: >-
            One entry per refused order in a batch. Present only on an error
            that a batch caused.
          items:
            $ref: '#/components/schemas/BatchOrderError'
          type:
            - array
            - 'null'
      required:
        - code
        - message
      type: object
    BucketLimit:
      description: 'One bucket''s limit: how many tokens it holds and how fast it refills.'
      properties:
        capacity:
          description: >-
            The most tokens the bucket holds. That is the largest burst you can
            send.
          format: int32
          minimum: 0
          type: integer
        refillPerSec:
          description: Tokens added per second, up to `capacity`.
          format: int32
          minimum: 0
          type: integer
      required:
        - capacity
        - refillPerSec
      type: object
    BatchOrderError:
      description: >-
        One rejected order within a batch placement: which order failed, and
        why.
      properties:
        index:
          description: Zero-based position in the request.
          minimum: 0
          type: integer
        outcomeId:
          description: The outcome ID of the rejected order.
          type: string
        reason:
          description: >-
            Human-readable. Not stable. Branch on the envelope's `code` and on
            `index`.
          type: string
      required:
        - index
        - outcomeId
        - reason
      type: object
  securitySchemes:
    keyId:
      description: The key's UUID.
      in: header
      name: Novig-Key-Id
      type: apiKey
    signature:
      description: Standard padded base64 of the NOVIG-V3 signature.
      in: header
      name: Novig-Signature
      type: apiKey
    timestamp:
      description: Unix milliseconds. ±30 s.
      in: header
      name: Novig-Timestamp
      type: apiKey

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.