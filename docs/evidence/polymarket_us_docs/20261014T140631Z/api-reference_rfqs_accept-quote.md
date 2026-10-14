> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Accept quote

> Accepts one side of a quote.



## OpenAPI

````yaml /api-reference/oapi-schemas/rfqs-schema.json put /v1/rfqs/{rfqId}/quotes/{quoteId}/accept
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
  /v1/rfqs/{rfqId}/quotes/{quoteId}/accept:
    put:
      tags:
        - RFQs
      summary: Accept quote
      description: Accepts one side of a quote.
      operationId: RFQAPI_AcceptQuote
      parameters:
        - name: rfqId
          in: path
          required: true
          schema:
            type: string
        - name: quoteId
          in: path
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RFQAPIAcceptQuoteBody'
        required: true
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/v1AcceptQuoteResponse'
components:
  schemas:
    RFQAPIAcceptQuoteBody:
      type: object
      properties:
        acceptedSide:
          $ref: '#/components/schemas/v1Side'
      required:
        - acceptedSide
    v1AcceptQuoteResponse:
      type: object
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