> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get all my positions

> Get a comprehensive overview of all positions held by the user, satisfying the provided parameters. This operation includes details about each position's size, entry price, and current market value. Results are limited to a maximum of 100 items by default.

**Rate limit:** 256 requests per second.



## OpenAPI

````yaml /deprecated/api-reference/spec-files/openapi31.json get /nbx/v2/emm/positions/all
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
  /nbx/v2/emm/positions/all:
    get:
      tags:
        - Positions
      summary: Get all my positions
      description: >-
        Get a comprehensive overview of all positions held by the user,
        satisfying the provided parameters. This operation includes details
        about each position's size, entry price, and current market value.
        Results are limited to a maximum of 100 items by default.


        **Rate limit:** 256 requests per second.
      operationId: getAllPositions
      parameters:
        - name: currency
          in: query
          description: The currency denomination
          required: true
          schema:
            type: string
            enum:
              - CASH
              - COIN
        - name: outcomeIds
          in: query
          description: >-
            Comma-separated list of outcome IDs to filter positions by, e.g.
            `outcomeIds=a,b,c`. If omitted, you will get all positions across
            open markets. An empty value matches nothing.
          required: false
          style: form
          explode: false
          schema:
            type: array
            items:
              type: string
      responses:
        '200':
          description: Successfully retrieved all positions for the user
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/PositionResponseDto'
        '400':
          description: Bad request
      x-code-samples:
        - lang: bash
          label: cURL Example
          source: |-
            curl -X GET '$API/emm/positions/all' \
              -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
              -G \
              --data-urlencode 'currency=COIN' \
              --data-urlencode 'outcomeIds=6bee554c-d5ee-4ada-b283-112746883542,8d18ea33-2953-469f-a5c9-d407d333529d'
components:
  schemas:
    PositionResponseDto:
      type: object
      properties:
        marketId:
          type: string
          description: The ID of the market this position is for
          example: 123e4567-e89b-12d3-a456-426614174000
        outcomeId:
          type: string
          description: The ID of the outcome this position is for
          example: 123e4567-e89b-12d3-a456-426614174001
        size:
          type: number
          description: The quantity of positive exposure to the outcome
          example: 100
        cost:
          type: number
          description: The net entry cost of the position
          example: 66.67
        currency:
          type: string
          description: The currency of the position
          example: COIN

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.