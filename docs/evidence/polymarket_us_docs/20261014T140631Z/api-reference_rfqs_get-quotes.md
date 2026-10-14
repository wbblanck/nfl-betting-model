> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get quotes

> Returns quotes matching the query filters.



## OpenAPI

````yaml /api-reference/oapi-schemas/rfqs-schema.json get /v1/rfqs/quotes
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
  /v1/rfqs/quotes:
    get:
      tags:
        - RFQs
      summary: Get quotes
      description: Returns quotes matching the query filters.
      operationId: RFQAPI_GetQuotes
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
            format: int32
            minimum: 1
            maximum: 100
            default: 100
        - name: cursor
          in: query
          required: false
          schema:
            type: string
        - name: quoteId
          in: query
          required: false
          schema:
            type: string
        - name: rfqId
          in: query
          required: false
          schema:
            type: string
        - name: status
          in: query
          required: false
          schema:
            type: string
            enum:
              - QUOTE_STATUS_ACTIVE
              - QUOTE_STATUS_CONFIRMED
              - QUOTE_STATUS_DELETED
              - QUOTE_STATUS_ACCEPTED
              - QUOTE_STATUS_EXECUTED
        - name: userFilter
          in: query
          required: false
          schema:
            type: string
            enum:
              - USER_FILTER_SELF
        - name: rfqUserFilter
          in: query
          required: false
          schema:
            type: string
            enum:
              - USER_FILTER_SELF
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/v1GetQuotesResponse'
components:
  schemas:
    v1GetQuotesResponse:
      type: object
      properties:
        quotes:
          type: array
          items:
            $ref: '#/components/schemas/v1Quote'
        cursor:
          type: string
    v1Quote:
      type: object
      properties:
        id:
          type: string
          description: Quote ID. Changes on replacement.
        rfqId:
          type: string
        creatorRfqUserId:
          type: string
        symbol:
          type: string
        status:
          $ref: '#/components/schemas/v1QuoteStatus'
        createdTime:
          type: string
          format: date-time
        buyPrice:
          type: string
          description: >-
            Price offered for a requester BUY order; the quote creator takes
            SELL.
        sellPrice:
          type: string
          description: >-
            Price offered for a requester SELL order; the quote creator takes
            BUY.
        restRemainder:
          type: boolean
        postOnly:
          type: boolean
        rfqCreatorUserId:
          type: string
        rfqCashOrderQty:
          type: string
          nullable: true
        buyQtyDecimal:
          type: string
        sellQtyDecimal:
          type: string
        updatedTime:
          type: string
          format: date-time
        acceptedSide:
          $ref: '#/components/schemas/v1Side'
        acceptedTime:
          type: string
          format: date-time
        confirmedTime:
          type: string
          format: date-time
        confirmationDeadline:
          type: string
          format: date-time
        executionDeadline:
          type: string
          format: date-time
          description: Scheduled time for paired requester and quoter order submission.
        executedTime:
          type: string
          format: date-time
          description: Durable execution-state timestamp.
        rfqCreatorOrderId:
          type: string
          description: >-
            Requester's exchange order ID. Visible to both requester and quoter
            when present.
          nullable: true
        creatorOrderId:
          type: string
          description: >-
            Quoter's exchange order ID. Visible to both requester and quoter
            when present.
          nullable: true
    v1QuoteStatus:
      type: string
      enum:
        - QUOTE_STATUS_ACTIVE
        - QUOTE_STATUS_CONFIRMED
        - QUOTE_STATUS_DELETED
        - QUOTE_STATUS_ACCEPTED
        - QUOTE_STATUS_EXECUTED
      description: QuoteStatus represents the current state of a quote.
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