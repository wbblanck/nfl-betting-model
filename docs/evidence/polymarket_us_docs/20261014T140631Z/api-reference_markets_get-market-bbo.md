> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Market BBO

> Retrieve current market data (best bid/offer, stats) for a specific market by its slug in a lightweight format



## OpenAPI

````yaml /api-reference/oapi-schemas/markets-schema.json get /v1/markets/{slug}/bbo
openapi: 3.0.3
info:
  title: protos/gateway/market/v1/market.proto
  version: 1.0.0
servers:
  - url: https://gateway.polymarket.us
    description: Production server
security: []
tags:
  - name: MarketService
paths:
  /v1/markets/{slug}/bbo:
    get:
      tags:
        - Markets
      summary: Get Market BBO
      description: >-
        Retrieve current market data (best bid/offer, stats) for a specific
        market by its slug in a lightweight format
      operationId: MarketService_GetMarketBBO
      parameters:
        - name: slug
          description: Market slug
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Market data lite including best bid/offer and stats
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gateway.market.v1.GetMarketBBOResponse'
        '404':
          description: Market not found
          content:
            application/json:
              schema: {}
        '500':
          description: Internal server error
          content:
            application/json:
              schema: {}
components:
  schemas:
    gateway.market.v1.GetMarketBBOResponse:
      type: object
      properties:
        marketData:
          $ref: '#/components/schemas/shared.market_data.v1.MarketDataLite'
      description: Response containing market BBO data in a lightweight format
    shared.market_data.v1.MarketDataLite:
      type: object
      properties:
        marketSlug:
          type: string
        currentPx:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        lastTradePx:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        settlementPx:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        sharesTraded:
          type: string
        openInterest:
          type: string
        bestAsk:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        bestBid:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        askDepth:
          type: integer
          format: int32
        bidDepth:
          type: integer
          format: int32
        lastPriceSample:
          $ref: '#/components/schemas/shared.market_data.v1.PriceSample'
        longQuote:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        shortQuote:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        state:
          $ref: '#/components/schemas/shared.market_data.v1.MarketState'
        bidShares:
          type: string
          description: >-
            Total shares resting on the bid side: every level's positive
            quantity

            summed, rounded down to two significant figures, the same contract
            as

            the unified market frame so both surfaces show one number. "0" when
            the

            side is empty; unset on a frame from a producer that predates this

            field. bid_depth counts price levels, not shares.
        askShares:
          type: string
          description: |-
            Total shares resting on the offer side, same rounding and empty
            convention as bid_shares.
    gateway.types.v1.Amount:
      type: object
      properties:
        value:
          type: string
          format: decimal
          example: 123.45
          description: The amount as a decimal string.
        currency:
          type: string
          description: The currency code
      description: Represents a monetary amount with its currency.
      required:
        - value
        - currency
    shared.market_data.v1.PriceSample:
      type: object
      properties:
        longPx:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        shortPx:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        ts:
          type: string
          format: date-time
    shared.market_data.v1.MarketState:
      type: string
      enum:
        - MARKET_STATE_OPEN
        - MARKET_STATE_PREOPEN
        - MARKET_STATE_SUSPENDED
        - MARKET_STATE_EXPIRED
        - MARKET_STATE_TERMINATED
        - MARKET_STATE_HALTED
        - MARKET_STATE_MATCH_AND_CLOSE_AUCTION

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.