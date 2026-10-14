> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Modify Multiple Orders

> Modify up to 20 existing orders in a single request. Each entry is forwarded to the exchange as a cancel-replace. If any entry fails request-shape validation, the whole batch is rejected by the gateway before reaching the exchange. The exchange may silently ignore unknown `orderId`s. `modifiedOrderIds` is an echo of the request, not a confirmation; observe actual outcomes on the order stream.



## OpenAPI

````yaml /api-reference/oapi-schemas/orders-schema.json post /v1/orders/batched/modify
openapi: 3.0.1
info:
  title: Orders API
  description: >-
    Order management endpoints for trading. All endpoints require Ed25519
    signature authentication.
  version: v1.0.0
servers:
  - url: https://api.polymarket.us
security:
  - X-PM-Access-Key: []
    X-PM-Timestamp: []
    X-PM-Signature: []
tags:
  - name: Orders
paths:
  /v1/orders/batched/modify:
    post:
      tags:
        - Orders
      summary: Modify Multiple Orders
      description: >-
        Modify up to 20 existing orders in a single request. Each entry is
        forwarded to the exchange as a cancel-replace. If any entry fails
        request-shape validation, the whole batch is rejected by the gateway
        before reaching the exchange. The exchange may silently ignore unknown
        `orderId`s. `modifiedOrderIds` is an echo of the request, not a
        confirmation; observe actual outcomes on the order stream.
      operationId: OrdersService_ModifyOrderList
      requestBody:
        description: Request to modify multiple orders in a single batched request
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ModifyOrderListRequest'
      responses:
        '200':
          description: Orders modified successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ModifyOrderListResponse'
        '400':
          description: >-
            Bad request - invalid batched modify request or exceeds max batch
            size
        '401':
          description: Unauthorized - invalid or missing authentication token
        '500':
          description: Internal server error
components:
  schemas:
    ModifyOrderListRequest:
      type: object
      required:
        - orders
      properties:
        orders:
          type: array
          minItems: 1
          maxItems: 20
          items:
            $ref: '#/components/schemas/ModifyOrderListEntry'
          description: Orders to modify (1 to 20).
      description: Batched modify-order request.
    ModifyOrderListResponse:
      type: object
      properties:
        modifiedOrderIds:
          type: array
          items:
            type: string
          description: >-
            Order IDs submitted for modification, in request order. Echo of the
            input, not a confirmation. Watch the order stream for actual
            outcomes.
    ModifyOrderListEntry:
      type: object
      required:
        - orderId
        - marketSlug
      properties:
        orderId:
          type: string
          description: Exchange-assigned order ID to modify.
        marketSlug:
          type: string
          description: Market slug the order belongs to.
        price:
          $ref: '#/components/schemas/Amount'
          description: New order price and currency
        quantity:
          type: number
          format: double
          description: >-
            New order quantity in contracts. Supports decimal quantities on
            markets whose minimumTradeQty is less than 1.
        tif:
          $ref: '#/components/schemas/TimeInForce'
          description: New order time in force
        participateDontInitiate:
          type: boolean
          description: Order must rest on the book prior to matching (maker only)
        goodTillTime:
          type: string
          description: Good till time for orders with TIME_IN_FORCE_GOOD_TILL_DATE
      description: >-
        Same shape as the body of `POST /v1/order/{orderId}/modify`, with
        `orderId` in the body instead of the URL path.
    Amount:
      type: object
      required:
        - value
        - currency
      properties:
        value:
          type: string
          format: decimal
          example: '0.55'
          description: The amount as a decimal string
        currency:
          type: string
          example: USD
          description: The currency code (e.g., 'USD')
      description: Represents a monetary amount with its currency
    TimeInForce:
      type: string
      enum:
        - TIME_IN_FORCE_DAY
        - TIME_IN_FORCE_GOOD_TILL_CANCEL
        - TIME_IN_FORCE_GOOD_TILL_DATE
        - TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
        - TIME_IN_FORCE_FILL_OR_KILL
      description: >-
        Time in force policy. `TIME_IN_FORCE_DAY` expires at end of trading day.
        `TIME_IN_FORCE_GOOD_TILL_CANCEL` (GTC) remains active until filled or
        canceled. `TIME_IN_FORCE_GOOD_TILL_DATE` (GTD) expires at specified
        time. `TIME_IN_FORCE_IMMEDIATE_OR_CANCEL` (IOC) fills immediately or
        cancels remaining. `TIME_IN_FORCE_FILL_OR_KILL` (FOK) must fill entirely
        or cancel.
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
        [Authentication](/api/authentication) for details.

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.