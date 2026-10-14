> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Create combo

> Creates or returns the combo instrument for the supplied legs. Each authenticated exchange participant may create up to 1,000 new combo instruments per week across all of its accounts. The quota resets Monday at 00:00 UTC. Returning an existing canonical combo does not consume the quota.



## OpenAPI

````yaml /institutional/oapi-schemas/combos-schema.json post /v1/combos
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
    post:
      tags:
        - Combos
      summary: Create combo
      description: >-
        Creates or returns the combo instrument for the supplied legs. Each
        authenticated exchange participant may create up to 1,000 new combo
        instruments per week across all of its accounts. The quota resets Monday
        at 00:00 UTC. Returning an existing canonical combo does not consume the
        quota.
      operationId: ComboAPI_CreateCombo
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/v1CreateComboRequest'
        required: true
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/v1CreateComboResponse'
components:
  schemas:
    v1CreateComboRequest:
      type: object
      properties:
        legs:
          type: array
          items:
            $ref: '#/components/schemas/v1ComboLeg'
          minItems: 2
          maxItems: 50
      required:
        - legs
    v1CreateComboResponse:
      type: object
      properties:
        combo:
          $ref: '#/components/schemas/v1ComboInstrument'
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
    v1Side:
      type: string
      enum:
        - SIDE_BUY
        - SIDE_SELL
      description: Side indicates the side of an Order.
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
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.