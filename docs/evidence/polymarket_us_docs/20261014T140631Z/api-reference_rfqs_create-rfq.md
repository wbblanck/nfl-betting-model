> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Create RFQ

> Creates a combo RFQ using the authenticated Retail account.



## OpenAPI

````yaml /api-reference/oapi-schemas/rfqs-schema.json post /v1/rfqs
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
  /v1/rfqs:
    post:
      tags:
        - RFQs
      summary: Create RFQ
      description: Creates a combo RFQ using the authenticated Retail account.
      operationId: RFQAPI_CreateRFQ
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/v1CreateRFQRequest'
        required: true
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/v1CreateRFQResponse'
components:
  schemas:
    v1CreateRFQRequest:
      type: object
      properties:
        qtyDecimal:
          type: string
        cashOrderQty:
          type: string
        symbol:
          type: string
        restRemainder:
          type: boolean
      required:
        - symbol
        - restRemainder
      oneOf:
        - required:
            - qtyDecimal
        - required:
            - cashOrderQty
    v1CreateRFQResponse:
      type: object
      properties:
        rfqId:
          type: string
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