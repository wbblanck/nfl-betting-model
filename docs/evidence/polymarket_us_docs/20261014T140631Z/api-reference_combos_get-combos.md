> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get combos

> Returns the combo matching the exact symbol.



## OpenAPI

````yaml /institutional/oapi-schemas/combos-schema.json get /v1/combos
openapi: 3.0.3
info:
  title: Combos API
  version: v1.0.0
servers:
  - url: https://api.prod.polymarketexchange.com
    description: Production server
security:
  - bearerAuth: []
tags:
  - name: Combos
    description: Create and read combo instruments.
paths:
  /v1/combos:
    get:
      tags:
        - Combos
      summary: Get combos
      description: Returns the combo matching the exact symbol.
      operationId: ComboAPI_GetCombos
      parameters:
        - name: symbol
          in: query
          required: true
          schema:
            type: string
            minLength: 1
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/v1GetCombosResponse'
components:
  schemas:
    v1GetCombosResponse:
      type: object
      properties:
        combos:
          type: array
          items:
            $ref: '#/components/schemas/v1ComboInstrument'
    v1ComboInstrument:
      type: object
      properties:
        id:
          type: string
        legs:
          type: array
          items:
            $ref: '#/components/schemas/v1ComboLeg'
        state:
          $ref: '#/components/schemas/v1InstrumentState'
        createdTime:
          type: string
          format: date-time
        tickSize:
          type: number
          format: double
    v1ComboLeg:
      type: object
      properties:
        symbol:
          type: string
        side:
          $ref: '#/components/schemas/v1Side'
      required:
        - symbol
        - side
    v1InstrumentState:
      type: string
      enum:
        - INSTRUMENT_STATE_CLOSED
        - INSTRUMENT_STATE_OPEN
        - INSTRUMENT_STATE_PREOPEN
        - INSTRUMENT_STATE_SUSPENDED
        - INSTRUMENT_STATE_EXPIRED
        - INSTRUMENT_STATE_TERMINATED
        - INSTRUMENT_STATE_HALTED
        - INSTRUMENT_STATE_MATCH_AND_CLOSE_AUCTION
        - INSTRUMENT_STATE_PENDING
      description: InstrumentState represents the state of an instrument.
    v1Side:
      type: string
      enum:
        - SIDE_BUY
        - SIDE_SELL
      description: Side indicates the side of an Order.
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.