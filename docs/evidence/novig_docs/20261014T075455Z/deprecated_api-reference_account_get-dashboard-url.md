> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get dashboard URL

> Issue a single-use, presigned URL to the EMM analytics dashboard for the authenticated trader.

The returned URL opens the Novig analytics dashboard (P&L, fills, open exposure, etc.) in a browser. The dashboard is scoped to the authenticated trader — you only ever see your own rows.

- **Single-use:** each URL may be redeemed once. To view refreshed data, call this endpoint again for a new URL.
- **Redeem immediately:** the URL must be opened within approximately 90 seconds of issuance. Mint a URL at the moment you need it — do not request URLs ahead of time, cache them, or hand them to a background job.
- **`expiresAt`:** see the field note in the response schema. It does not currently describe the redemption window, so do not use it to schedule refreshes.

**Rate limit:** 64 requests per second.



## OpenAPI

````yaml /deprecated/api-reference/spec-files/openapi31.json get /nbx/v2/emm/account/dashboard
openapi: 3.1.0
info:
  title: NBX API
  description: >+
    ## API Overview


    The NBX API is designed with two interfaces:


    - **REST API**
      - **URL:**          `https://api.novig.com/nbx/v2`
      - **Constraints:**
        - **Rate limits:**
          - Single-order placement: 2048 requests per second
          - Batch placement: 64 requests per second
          - Order cancellation: 2048 requests per second
          - Kill switch: 1 request per 30 seconds
          - Data retrieval: 256 requests per second
          - User history (`/fills`, `/orders`, `/transactions`): 32 requests/second burst, 512 requests/minute sustained
        - **Timeout:**    5 seconds
      - **Features:**
        - Place, cancel, and query orders.
        - Retrieve market data and positions.
        - Manage account settings and balances.
      - **Best Practices:**
        - Use appropriate HTTP methods.
        - Include `Authorization` and `Content-Type` headers.
        - Implement exponential backoff for handling rate limits and robust error handling.

    - **WebSocket API**
      - **URL:**          `wss://api.novig.com/tape`
      - **Constraints:**
        - **Keepalive:** protocol-level WebSocket Ping every 15 seconds; standard clients respond automatically, and a client that misses a full interval is disconnected
      - **Features:**
        - Real-time order book ticks.
        - Real-time market lifecycle updates.
        - Private place, fill, and cancel notifications.
        - Protocol-level heartbeat to ensure connection health.
      - **Best Practices:**
        - Implement reconnection logic with exponential backoff.
        - Process messages sequentially to maintain order book integrity.
        - Appropriately handle various event types.
        - Subscribe to specific market events or to the global tape.

    ## Authentication


    The NBX API uses [**OAuth 2.0 Client
    Credentials**](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow)
    with JSON Web Tokens (JWT).


    1. **Obtain Credentials:** Request your client ID and secret from Novig.

    2. **Request an Access Token:** Send a POST request to the OAuth endpoint.
    For example:

    ```bash

    curl 
      --request POST 
      --url https://auth.novig.us/oauth/token 
      --header "Content-Type: application/json" 
      --data '{ 
        "audience"      : "https://api.novig.us", 
        "grant_type"    : "client_credentials", 
        "client_id"     : "YOUR_CLIENT_ID", 
        "client_secret" : "YOUR_CLIENT_SECRET" 
      }'
    ```

    3. **Use the Token:** Include the token in your requests by setting the HTTP
    header:

    ```bash

    Authorization: Bearer YOUR_ACCESS_TOKEN

    ```


    > **Note:** For integration in the QA environment, you'll need to use
    different endpoints:

    > - **Issuer:** `https://auth-qa.novig.us`

    > - **Audience:** `https://api-qa.novig.us`

    > - **API Base URL:** `https://api-qa.novig.us`

  version: 0.0.44
  contact:
    name: Contact
    url: https://novig.com
    email: tech@novig.com
servers:
  - url: https://api.novig.com
    description: Production
  - url: https://api-qa.novig.us
    description: QA
security: []
tags:
  - name: Orders
    description: Endpoints for managing orders and trades
  - name: Markets
    description: Endpoints for accessing market data and order books
  - name: Events
    description: Endpoints for discovering events and fetching event-related data
  - name: Account
    description: Endpoints for managing account settings and balances
  - name: Positions
    description: Endpoints for accessing positions and fills
  - name: WebSockets
    description: Channels for real-time market data and order updates
paths:
  /nbx/v2/emm/account/dashboard:
    get:
      tags:
        - Account
      summary: Get dashboard URL
      description: >-
        Issue a single-use, presigned URL to the EMM analytics dashboard for the
        authenticated trader.


        The returned URL opens the Novig analytics dashboard (P&L, fills, open
        exposure, etc.) in a browser. The dashboard is scoped to the
        authenticated trader — you only ever see your own rows.


        - **Single-use:** each URL may be redeemed once. To view refreshed data,
        call this endpoint again for a new URL.

        - **Redeem immediately:** the URL must be opened within approximately 90
        seconds of issuance. Mint a URL at the moment you need it — do not
        request URLs ahead of time, cache them, or hand them to a background
        job.

        - **`expiresAt`:** see the field note in the response schema. It does
        not currently describe the redemption window, so do not use it to
        schedule refreshes.


        **Rate limit:** 64 requests per second.
      operationId: getDashboardUrl
      parameters: []
      responses:
        '200':
          description: Dashboard URL issued.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DashboardUrlResponseDto'
      x-code-samples:
        - lang: bash
          label: cURL Example
          source: |-
            curl -X GET "$API/emm/account/dashboard" \
              -H "Authorization: Bearer $TOKEN"
components:
  schemas:
    DashboardUrlResponseDto:
      type: object
      properties:
        url:
          type: string
          format: uri
          description: >-
            Presigned, single-use URL to the EMM analytics dashboard. Open it in
            a browser immediately after issuance; request a new URL to view
            refreshed data.
          example: >-
            https://app.hex.tech/embed/<project-id>/?presigned_url_token=eyJhbGciOi...
        expiresAt:
          type: string
          format: date-time
          description: >-
            ISO-8601 timestamp returned alongside the URL.


            > **Note:** this value currently reports 24 hours after issuance,
            which does not match the URL's actual redemption window of
            approximately 90 seconds. Do not use `expiresAt` to schedule
            refreshes — mint a new URL immediately before each use.
          example: '2026-05-22T15:04:05.000Z'
      required:
        - url
        - expiresAt

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.