> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# List market history

> | | |
| --- | --- |
| **Key** | `any` |
| **Throttle** | `history` |
| **Cost** | `4 + 1 per 50 rows` |
| **Answers** | <span class="st st-ok">200</span> <span class="st st-warn">400</span> <span class="st st-warn">401</span> <span class="st st-warn">403</span> <span class="st st-hold">423</span> <span class="st st-hold">429</span> <span class="st st-warn">451</span> |
| **Idempotent** | `true` |



## OpenAPI

````yaml /api-reference/spec-files/openapi-v3.json get /v3/history/markets
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
  /v3/history/markets:
    get:
      tags:
        - History
      summary: List market history
      description: >-
        | | |

        | --- | --- |

        | **Key** | `any` |

        | **Throttle** | `history` |

        | **Cost** | `4 + 1 per 50 rows` |

        | **Answers** | <span class="st st-ok">200</span> <span class="st
        st-warn">400</span> <span class="st st-warn">401</span> <span class="st
        st-warn">403</span> <span class="st st-hold">423</span> <span class="st
        st-hold">429</span> <span class="st st-warn">451</span> |

        | **Idempotent** | `true` |
      operationId: listHistoricalMarkets
      parameters:
        - description: >-
            Exclusive lower bound on the market's most recent settlement.
            Excludes unsettled markets.
          example: 1756512000000
          in: query
          name: settledAfter
          required: false
          schema:
            format: int64
            type: integer
        - description: >-
            Page size. Defaults to **500**, not the maximum. 1 to 5000. A value
            outside that range

            answers `400`.
          in: query
          name: limit
          required: false
          schema:
            default: 500
            format: int32
            maximum: 5000
            minimum: 1
            type: integer
        - description: The `next` cursor from the previous page. Opaque.
          in: query
          name: after
          required: false
          schema:
            type: string
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Page_HistoricalMarketResponse'
          description: >-
            One page of markets, newest first. With `settledAfter`, most recent
            settlement first.
        '400':
          content:
            application/json:
              example:
                code: PAGE_LIMIT_OUT_OF_RANGE
                message: Limit must be between 1 and 5000
              schema:
                $ref: '#/components/schemas/ErrorBody'
          description: The request is malformed.
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

            REQ_PATH="/v3/history/markets"
            QUERY="limit=100"
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
                let path = "/v3/history/markets";
                let url = format!("{HOST}{path}?limit=100");
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

            path = "/v3/history/markets"
            query = "limit=100"
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
            url = f"{HOST}{path}?{query}"
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

            const path = "/v3/history/markets";
            const query = "limit=100";
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
            const url = `${HOST}${path}?${query}`;
            const r = await fetch(url, {
              method: "GET",
              headers,
            });
            console.log(await r.text());
components:
  schemas:
    Page_HistoricalMarketResponse:
      allOf:
        - $ref: '#/components/schemas/PageCursorResponse'
        - properties:
            items:
              items:
                description: A market of any age and status.
                properties:
                  description:
                    description: Human-readable. Use it for discovery, never as a contract.
                    type: string
                  eventId:
                    description: ID of the event the market belongs to.
                    format: uuid
                    type: string
                  fee:
                    $ref: '#/components/schemas/MarketFee'
                    description: >-
                      What a taker pays on this market. Read it per market.
                      Never derive it from a league list.
                  marketId:
                    description: Market ID.
                    format: uuid
                    type: string
                  marketType:
                    description: A canonical name from `GET /v3/types/markets`.
                    example: MONEY
                    type: string
                  outcomes:
                    description: >-
                      Outcomes of the market. A graded outcome carries its grade
                      in `status`.
                    items:
                      $ref: '#/components/schemas/Outcome'
                    type: array
                  settledTs:
                    description: >-
                      Unix milliseconds of the most recent settlement. A
                      re-settlement updates it. Absent on an

                      unsettled market.
                    example: 1756512000000
                    format: int64
                    type: integer
                  status:
                    $ref: '#/components/schemas/MarketStatus'
                    description: Lifecycle status of a market.
                  strike:
                    description: >-
                      The line the market settles against, a decimal string. A
                      spread's line is the home side's

                      handicap. Absent on a market without a line.
                    example: '-3.5'
                    type: string
                  voids:
                    $ref: '#/components/schemas/Voidability'
                    description: >-
                      How a market settles if it voids. `PUSH` refunds every
                      fill at its cost. `FMV` settles every

                      outcome at its fair market value. The exchange never
                      pushes an `FMV` market. Do not assume a

                      refund.
                required:
                  - marketId
                  - description
                  - eventId
                  - marketType
                  - status
                  - voids
                  - fee
                  - outcomes
                type: object
              type: array
          required:
            - items
          type: object
      description: >-
        One page of a listing: the items in the listing's order, then the link
        to

        the next page. Every paged route answers this shape.
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
    PageCursorResponse:
      description: The link to the next page of a listing.
      properties:
        next:
          description: >-
            Pass it as `after` for the next page. Opaque: do not build or parse
            one. Absent on the last page.
          type: string
      type: object
    MarketFee:
      description: >-
        What a taker pays on this market. Read it per market. Never derive it
        from a league list.
      properties:
        charged:
          $ref: '#/components/schemas/Chargeability'
        coefficient:
          description: '`c` in the fee formula, a decimal string.'
          type: string
        makerCredit:
          description: >-
            The maker's share of the taker's fee on the same fill, a decimal
            string.
          type: string
      required:
        - coefficient
        - makerCredit
        - charged
      type: object
    Outcome:
      description: 'One outcome of a market: what an order names.'
      properties:
        name:
          description: Display name. Not a contract.
          type: string
        outcomeId:
          format: uuid
          type: string
        status:
          description: >-
            `TBD`, `WIN`, `LOSS`, `PUSH`, **or a decimal price string** between
            `"0.000"` and

            `"1.000"` when the market settles at fair market value. Not an enum.
            Branch on the four

            keywords. Treat anything else as a price.
          type: string
      required:
        - outcomeId
        - name
        - status
      type: object
    MarketStatus:
      description: Lifecycle status of a market.
      enum:
        - OPEN
        - CLOSED
        - SETTLED
      type: string
    Voidability:
      description: >-
        How a market settles if it voids. `PUSH` refunds every fill at its cost.
        `FMV` settles every outcome at its fair market value. The exchange never
        pushes an `FMV` market. Do not assume a refund.
      enum:
        - PUSH
        - FMV
      type: string
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
    Chargeability:
      description: >-
        When a market charges its taker. `WHEN_LIVE` charges only while the
        event is `OPEN_INGAME`. An eligible futures market charges `ALWAYS`,
        because its event never goes live. A PGA, ATP, WTA, UFC, F1 or NASCAR
        future carries no futures trading fee. It reads `WHEN_LIVE` and never
        charges.
      enum:
        - ALWAYS
        - WHEN_LIVE
      type: string
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