> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Create quote

> Creates a quote using the authenticated Retail account. Every successful call returns a new quoteId, including replacements. See [quote replacement](/api-reference/rfqs/overview#replace-a-quote).



## OpenAPI

````yaml /api-reference/oapi-schemas/rfqs-schema.json post /v1/rfqs/quotes
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
    post:
      tags:
        - RFQs
      summary: Create quote
      description: >-
        Creates a quote using the authenticated Retail account. Every successful
        call returns a new quoteId, including replacements. See [quote
        replacement](/api-reference/rfqs/overview#replace-a-quote).
      operationId: RFQAPI_CreateQuote
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/v1CreateQuoteRequest'
        required: true
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/v1CreateQuoteResponse'
components:
  schemas:
    v1CreateQuoteRequest:
      type: object
      properties:
        rfqId:
          type: string
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
      required:
        - rfqId
        - buyPrice
        - sellPrice
        - restRemainder
    v1CreateQuoteResponse:
      type: object
      properties:
        quoteId:
          type: string
          description: >-
            New quote ID. Changes on every successful CreateQuote, including
            replacements.
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