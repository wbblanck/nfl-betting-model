> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Cancel order batch

> Cancel up to 1024 orders by ID. Each order must belong to the trader associated with the API key.

We cancel every resting order in the request. The status code summarizes the batch:

- `200`: we sent a cancel for every ID.
- `207`: we found every ID. Some orders were already filled, cancelled, or rejected. `notCanceled` lists them with that status.
- `404`: at least one ID does not match an order of yours. `notCanceled` lists it with reason `NOT_FOUND`.

A new order reads as `NOT_FOUND` until its `place` event arrives on your private WebSocket channel. Wait for that event, then cancel again.

This operation is idempotent. It does not guarantee that the cancel reaches the matching engine before a fill. To confirm a cancel, consume the matching tape and rebuild the order book from it.
> **Note:** An entry under `canceled` means we sent the cancel. It does **not** mean the order is cancelled.

**Rate limit:** 2048 requests per second.



## OpenAPI

````yaml /deprecated/api-reference/spec-files/openapi31.json delete /nbx/v2/emm/orders/batch
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
  /nbx/v2/emm/orders/batch:
    delete:
      tags:
        - Orders
      summary: Cancel order batch
      description: >-
        Cancel up to 1024 orders by ID. Each order must belong to the trader
        associated with the API key.


        We cancel every resting order in the request. The status code summarizes
        the batch:


        - `200`: we sent a cancel for every ID.

        - `207`: we found every ID. Some orders were already filled, cancelled,
        or rejected. `notCanceled` lists them with that status.

        - `404`: at least one ID does not match an order of yours. `notCanceled`
        lists it with reason `NOT_FOUND`.


        A new order reads as `NOT_FOUND` until its `place` event arrives on your
        private WebSocket channel. Wait for that event, then cancel again.


        This operation is idempotent. It does not guarantee that the cancel
        reaches the matching engine before a fill. To confirm a cancel, consume
        the matching tape and rebuild the order book from it.

        > **Note:** An entry under `canceled` means we sent the cancel. It does
        **not** mean the order is cancelled.


        **Rate limit:** 2048 requests per second.
      operationId: cancelMultipleOrders
      parameters: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: array
              items:
                type: string
                description: The server-generated UUID of the order to be cancelled
                example: 123e4567-e89b-12d3-a456-426614174000
      responses:
        '200':
          description: We sent a cancel for every order.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CancelBatchResponse'
        '207':
          description: >-
            We found every ID. Some orders were already terminal. See
            `notCanceled`.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CancelBatchResponse'
        '400':
          description: Bad request
        '404':
          description: At least one ID does not match an order of yours. See `notCanceled`.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CancelBatchResponse'
      x-code-samples:
        - lang: bash
          label: cURL Example
          source: |-
            curl -X DELETE "localhost:80/nbx/v2/emm/orders/batch" \
              -H "Authorization: Bearer $TOKEN" \
              -H "Content-Type: application/json" \
              -d '[
                "550e8400-e29b-41d4-a716-446655440001",
                "550e8400-e29b-41d4-a716-446655440002",
                "550e8400-e29b-41d4-a716-446655440003"
            ]'
components:
  schemas:
    CancelBatchResponse:
      type: object
      description: >-
        The result of a batch cancel. `200`: we cancelled every order. `207`: we
        skipped some orders, see `notCanceled`. `404`: we did not find an ID.
      properties:
        canceled:
          type: array
          description: The orders we sent a cancel for, in request order
          items:
            $ref: '#/components/schemas/OrderResponseDto'
        notCanceled:
          type: array
          description: The IDs we sent no cancel for, in request order, each with a reason
          items:
            $ref: '#/components/schemas/NotCanceled'
      required:
        - canceled
        - notCanceled
    OrderResponseDto:
      type: object
      properties:
        id:
          type: string
          description: The unique identifier of the order
          example: 123e4567-e89b-12d3-a456-426614174002
        outcomeId:
          type: string
          description: The ID of the outcome associated with this order
          example: 123e4567-e89b-12d3-a456-426614174000
        marketId:
          type: string
          description: The ID of the market associated with this order
          example: 123e4567-e89b-12d3-a456-426614174003
        price:
          type: number
          description: The limit price at which the order is placed
          example: 0.125
        qty:
          type: number
          description: >-
            The remaining quantity of the order, denominated in Minimum Currency
            Units
          example: 4200
        originalQty:
          type: number
          description: >-
            The original quantity of the order, denominated in Minimum Currency
            Units
          example: 4200
        currency:
          type: string
          description: The currency in which the order is denominated
          example: COIN
        timestamp:
          type: string
          description: The timestamp when the order was placed
          example: '2023-10-05T12:00:00Z'
        status:
          type: string
          description: The current status of the order
          example: FILLED
        flags:
          type: string
          description: The trader-specified metadata associated with the order
          example: ABC12345
    NotCanceled:
      type: object
      description: One order ID from the request that we sent no cancel for
      properties:
        id:
          type: string
          description: The ID as given in the request
          example: 123e4567-e89b-12d3-a456-426614174002
        reason:
          $ref: '#/components/schemas/NotCanceledReason'
      required:
        - id
        - reason
    NotCanceledReason:
      type: string
      description: >-
        Why we skipped an ID: `NOT_FOUND`, or the stored status of an order the
        matcher has already completed
      enum:
        - NOT_FOUND
        - FILLED
        - CANCELED
        - REJECTED
      example: FILLED

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.