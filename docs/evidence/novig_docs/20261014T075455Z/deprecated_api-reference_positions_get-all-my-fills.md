> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get all my fills

> Access a complete list of all fills for the user, satisfying the provided parameters. This operation provides detailed records of each fill, including the quantity, price, and time of execution. Results are limited to a maximum of 256 items per request (default 100).

This endpoint covers **single contract fills** only. RFQs you quoted and won are a separate surface and do not appear here — list them with `GET /rfq/executions` (see [Execution Feed & Reconciliation](/api-reference/rfq/executions)).

**Rate limit:** 32 requests/second burst, 512 requests/minute sustained.



## OpenAPI

````yaml /deprecated/api-reference/spec-files/openapi31.json get /nbx/v2/emm/fills/all
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
  /nbx/v2/emm/fills/all:
    get:
      tags:
        - Positions
      summary: Get all my fills
      description: >-
        Access a complete list of all fills for the user, satisfying the
        provided parameters. This operation provides detailed records of each
        fill, including the quantity, price, and time of execution. Results are
        limited to a maximum of 256 items per request (default 100).


        This endpoint covers **single contract fills** only. RFQs you quoted and
        won are a separate surface and do not appear here — list them with `GET
        /rfq/executions` (see [Execution Feed &
        Reconciliation](/api-reference/rfq/executions)).


        **Rate limit:** 32 requests/second burst, 512 requests/minute sustained.
      operationId: getAllFills
      parameters:
        - name: currency
          in: query
          description: Currency of the fill
          required: false
          schema:
            type: string
            enum:
              - CASH
              - COIN
        - name: limit
          in: query
          description: Number of fills to return (max 256, default 100)
          required: false
          schema:
            type: integer
            maximum: 256
            default: 100
        - name: offset
          in: query
          description: Offset of the fills to return
          required: false
          schema:
            type: integer
        - name: beg
          in: query
          description: Beginning timestamp for filtering fills (UTC)
          required: false
          schema:
            type: string
            format: date-time
        - name: end
          in: query
          description: End timestamp for filtering fills (UTC)
          required: false
          schema:
            type: string
            format: date-time
        - name: marketStatus
          in: query
          description: Market status of the fill
          required: false
          schema:
            type: string
            enum:
              - OPEN
              - CLOSED
              - SETTLED
        - name: outcomeStatus
          in: query
          description: >-
            Outcome status of the fill. FMV matches every FMV-settled outcome,
            whatever its price.
          required: false
          schema:
            type: string
            enum:
              - TBD
              - WIN
              - LOSS
              - PUSH
              - FMV
      responses:
        '200':
          description: Successfully retrieved all fills for the user
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/FillResponseDto'
              example:
                - id: 01990f91-2d8a-7b6c-8a1e-4f5a6b7c8d90
                  orderId: 01990f88-3a1b-7d2c-8e4f-6a7b8c9d0e11
                  qty: 200
                  price: 0.61
                  isWash: false
                  isTaker: false
                  createdAt: '2026-09-03T18:40:02.917Z'
                  marketId: 01990e10-5b2c-7e4d-9f60-1a2b3c4d5e6f
                  outcomeId: 01990e10-5b2c-7e4d-9f60-1a2b3c4d5e71
                  outcomeStatus: '0.731'
                  transactions:
                    - id: 01990f91-2d8a-7b6c-8a1e-4f5a6b7c8d91
                      kind: FILL_STRAIGHT_MAKER_FUNDS
                      amount: '122'
                      createdAt: '2026-09-03T18:40:02.917Z'
        '400':
          description: Bad request
components:
  schemas:
    FillResponseDto:
      type: object
      properties:
        id:
          type: string
          description: The ID of the fill
          example: 123e4567-e89b-12d3-a456-426614174000
        orderId:
          type: string
          description: The ID of the order that was filled
          example: 123e4567-e89b-12d3-a456-426614174001
        price:
          type: number
          description: Price at which the fill executed, as a decimal probability
          example: 0.225
        qty:
          type: number
          description: Quantity filled, in minimum currency units (100 qty = 1.00 CASH)
          example: 75
        createdAt:
          type: string
          format: date-time
          description: The timestamp when the fill occurred
          example: '2023-10-05T12:00:00Z'
        isWash:
          type: boolean
          description: Whether the fill is a wash trade
          example: false
        isTaker:
          type: boolean
          description: Whether your filled order was the taker (true) or the maker (false)
          example: true
        marketId:
          type: string
          description: The ID of the related market
          example: 123e4567-e89b-12d3-a456-426614174002
        outcomeId:
          type: string
          description: The ID of the related outcome
          example: 123e4567-e89b-12d3-a456-426614174003
        outcomeStatus:
          type: string
          description: >-
            Grading status of the outcome the fill occurred on: `TBD`, `WIN`,
            `LOSS`, `PUSH`, or a decimal string like `0.731` for an outcome
            settled at fair market value (FMV). Reports the status at the time
            you read it, not at the time of the fill. Omitted on real-time
            `fill` events over the WebSocket private channel.
          example: '0.731'
        fee:
          type: string
          description: >-
            Total fee charged to you on this fill, as a decimal string in
            minimum currency units. Omitted when no fee was charged (maker
            fills, and fills matched while the event was not live), and on
            real-time `fill` events.
          example: '1.4274'
        transactions:
          type: array
          description: >-
            Ledger transactions between your wallet and this fill: the `FILL_*`
            collateral charge, the `FEE_*` fee when one was charged, and the
            `MAKER_CREDIT_STRAIGHT` maker credit when the fill earned one. Only
            your own wallet's transactions are listed — a maker never sees the
            taker's fee here. Omitted on real-time `fill` events; fetch the fill
            history to see them.
          items:
            $ref: '#/components/schemas/FillTransactionResponseDto'
      required:
        - id
        - orderId
        - price
        - qty
        - createdAt
        - isWash
        - isTaker
        - marketId
        - outcomeId
    FillTransactionResponseDto:
      type: object
      description: One ledger transaction between your wallet and a fill.
      properties:
        id:
          type: string
          description: The ID of the transaction
          example: 01990f91-2d8a-7b6c-8a1e-4f5a6b7c8d91
        kind:
          $ref: '#/components/schemas/FillTransactionKind'
        amount:
          type: string
          description: >-
            Amount of the transaction, as a positive decimal string in minimum
            currency units. `FILL_*` and `FEE_*` transactions debit your wallet
            by this amount; `MAKER_CREDIT_STRAIGHT` credits it. For a `FILL_*`
            charge this is your collateral, `price × qty` for the outcome you
            bought.
          example: '122'
        createdAt:
          type: string
          format: date-time
          description: The timestamp when the transaction was created
          example: '2026-09-03T18:40:02.917Z'
      required:
        - id
        - kind
        - amount
        - createdAt
    FillTransactionKind:
      type: string
      description: >-
        Which money movement a fill's ledger transaction is. `FILL_*` is the
        collateral funding the fill; `FEE_*` is the fee charged on it;
        `MAKER_CREDIT_STRAIGHT` is the maker credit paid to you for it. The
        remaining segments of `FILL_*` and `FEE_*` name the product
        (`STRAIGHT`), your role on the fill (`TAKER` or `MAKER`), for fees
        whether the event was live at match time (`LIVE` or `NONLIVE`), and the
        funding source (`FUNDS` for cash balance, `TRADE_CREDIT` for promotional
        credit). Under the current fee schedule only `FEE_STRAIGHT_TAKER_LIVE_*`
        fees are charged; the other `FEE_*` values are reserved.
      enum:
        - FILL_STRAIGHT_TAKER_FUNDS
        - FILL_STRAIGHT_TAKER_TRADE_CREDIT
        - FILL_STRAIGHT_MAKER_FUNDS
        - FILL_STRAIGHT_MAKER_TRADE_CREDIT
        - FEE_STRAIGHT_MAKER_LIVE_FUNDS
        - FEE_STRAIGHT_MAKER_NONLIVE_FUNDS
        - FEE_STRAIGHT_TAKER_LIVE_FUNDS
        - FEE_STRAIGHT_TAKER_NONLIVE_FUNDS
        - FEE_STRAIGHT_MAKER_LIVE_TRADE_CREDIT
        - FEE_STRAIGHT_MAKER_NONLIVE_TRADE_CREDIT
        - FEE_STRAIGHT_TAKER_LIVE_TRADE_CREDIT
        - FEE_STRAIGHT_TAKER_NONLIVE_TRADE_CREDIT
        - MAKER_CREDIT_STRAIGHT
      example: FILL_STRAIGHT_MAKER_FUNDS

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.