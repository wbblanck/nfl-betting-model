> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get all my orders

> Get a list of all orders associated with the user, satisfying the provided parameters. Results are limited to a maximum of 1024 items per request (default 100).

**Rate limit:** 32 requests/second burst, 512 requests/minute sustained.



## OpenAPI

````yaml /deprecated/api-reference/spec-files/openapi31.json get /nbx/v2/emm/orders/all
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
  /nbx/v2/emm/orders/all:
    get:
      tags:
        - Orders
      summary: Get all my orders
      description: >-
        Get a list of all orders associated with the user, satisfying the
        provided parameters. Results are limited to a maximum of 1024 items per
        request (default 100).


        **Rate limit:** 32 requests/second burst, 512 requests/minute sustained.
      operationId: getAllOrders
      parameters:
        - name: currency
          in: query
          description: Currency of the order
          required: false
          schema:
            type: string
            enum:
              - CASH
              - COIN
        - name: status
          in: query
          description: Status of the order
          required: false
          schema:
            type: string
        - name: limit
          in: query
          description: Number of orders to return (max 1024, default 100)
          required: false
          schema:
            type: integer
            maximum: 1024
            default: 100
        - name: offset
          in: query
          description: Offset of the orders to return
          required: false
          schema:
            type: integer
        - name: beg
          in: query
          description: Beginning timestamp for filtering orders (UTC)
          required: false
          schema:
            type: string
            format: date-time
        - name: end
          in: query
          description: End timestamp for filtering orders (UTC)
          required: false
          schema:
            type: string
            format: date-time
        - name: marketStatus
          in: query
          description: Market status of the order
          required: false
          schema:
            type: string
            enum:
              - OPEN
              - CLOSED
              - SETTLED
        - name: outcomeStatus
          in: query
          description: Outcome status of the order
          required: false
          schema:
            type: string
            enum:
              - TBD
              - WIN
              - LOSS
              - PUSH
      responses:
        '200':
          description: Successfully retrieved all orders for the user
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/OrderResponseDto'
        '400':
          description: Bad request
components:
  schemas:
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

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.