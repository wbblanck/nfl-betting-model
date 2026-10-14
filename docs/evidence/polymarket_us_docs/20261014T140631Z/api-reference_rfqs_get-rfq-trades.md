> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get RFQ trades

> Returns anonymous original fills where either order originated from an RFQ, newest first. Includes single instruments, combos, and later fills on resting orders. Repeat the same filters and limit with each cursor; an empty cursor ends the traversal. History is eventually visible. Requery overlapping time windows to find late arrivals and deduplicate by tradeId. Later corrections and busts do not amend these prints.



## OpenAPI

````yaml /api-reference/oapi-schemas/rfqs-schema.json get /v1/rfqs/trades
openapi: 3.0.3
info:
  title: RFQ API
  version: v1.0.0
  description: Read RFQ trades and manage combo RFQs and quotes through the Retail API.
servers:
  - url: https://api.polymarket.us
    description: Production server
security:
  - X-PM-Access-Key: []
    X-PM-Timestamp: []
    X-PM-Signature: []
tags:
  - name: RFQs
    description: Read RFQ trades and manage combo RFQs and quotes.
paths:
  /v1/rfqs/trades:
    get:
      tags:
        - RFQs
      summary: Get RFQ trades
      description: >-
        Returns anonymous original fills where either order originated from an
        RFQ, newest first. Includes single instruments, combos, and later fills
        on resting orders. Repeat the same filters and limit with each cursor;
        an empty cursor ends the traversal. History is eventually visible.
        Requery overlapping time windows to find late arrivals and deduplicate
        by tradeId. Later corrections and busts do not amend these prints.
      operationId: RFQAPI_GetRFQTrades
      parameters:
        - name: limit
          description: >-
            Page size. Omitted or zero defaults to 100; otherwise between 1 and
            100.
          in: query
          required: false
          schema:
            type: integer
            format: int32
            minimum: 0
            maximum: 100
            default: 100
        - name: cursor
          description: Opaque continuation. Repeat the same participant, filters and limit.
          in: query
          required: false
          schema:
            type: string
        - name: startTime
          description: >-
            Inclusive execution time. Defaults to the start of available
            history.
          in: query
          required: false
          schema:
            type: string
            format: date-time
        - name: endTime
          description: >-
            Exclusive execution time. Defaults to receipt time of the first
            request.
          in: query
          required: false
          schema:
            type: string
            format: date-time
        - name: symbol
          description: Exact, case-sensitive instrument symbol. Empty selects all symbols.
          in: query
          required: false
          schema:
            type: string
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/v1GetRFQTradesResponse'
components:
  schemas:
    v1GetRFQTradesResponse:
      type: object
      properties:
        trades:
          type: array
          items:
            $ref: '#/components/schemas/v1RFQTrade'
          description: Ordered by execution time descending, then trade ID descending.
        cursor:
          type: string
          description: >-
            Empty ends this traversal. Continue nonempty cursors even after
            empty pages.
    v1RFQTrade:
      type: object
      properties:
        tradeId:
          type: string
        symbol:
          type: string
        price:
          type: string
        qtyDecimal:
          type: string
        aggressorSide:
          $ref: '#/components/schemas/v1Side'
        executedTime:
          type: string
          format: date-time
      description: >-
        An anonymous original fill. Later trade corrections are not reflected
        here.
    v1Side:
      type: string
      enum:
        - SIDE_BUY
        - SIDE_SELL
      description: Side indicates the side of an Order.
  securitySchemes:
    X-PM-Access-Key:
      type: apiKey
      in: header
      name: X-PM-Access-Key
      description: >-
        Your API key ID (UUID). Generate at
        [polymarket.us/developer](https://polymarket.us/developer).
    X-PM-Timestamp:
      type: apiKey
      in: header
      name: X-PM-Timestamp
      description: >-
        Unix timestamp in milliseconds. Must be within 30 seconds of server
        time.
    X-PM-Signature:
      type: apiKey
      in: header
      name: X-PM-Signature
      description: >-
        Base64-encoded Ed25519 signature of `timestamp + method + path`. See
        [Authentication](/api-reference/authentication) for details.

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.