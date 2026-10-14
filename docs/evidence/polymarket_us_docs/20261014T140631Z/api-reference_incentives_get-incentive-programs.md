> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Incentive Programs

> Returns incentive programs grouped by market, with time periods.



## OpenAPI

````yaml /institutional/oapi-schemas/incentives-schema.json get /v1/incentives
openapi: 3.0.3
info:
  title: Incentives API
  version: v1.0.0
servers:
  - url: https://api.prod.polymarketexchange.com
    description: Production server
security:
  - bearerAuth: []
tags:
  - name: Incentives
paths:
  /v1/incentives:
    get:
      tags:
        - Incentives
      summary: Get Incentive Programs
      description: Returns incentive programs grouped by market, with time periods.
      operationId: IncentivesAPI_ListIncentives
      parameters:
        - name: pageSize
          in: query
          required: false
          schema:
            type: integer
            format: int32
          description: >-
            Number of markets to return per page. Use with `pageToken` for
            pagination. Example: `10`
        - name: pageToken
          in: query
          required: false
          schema:
            type: string
          description: >-
            Pagination token from a previous response's `nextPageToken` field.
            Omit for the first request
        - name: symbols
          description: >-
            Filter by market symbols. Returns only programs for the specified
            markets. Example: `aec-nba-bos-nyk-2026-04-01`
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: orderBy
          description: >-
            Field to sort results by. `created_at` sorts by program start time,
            `reward` sorts by reward pool size
          in: query
          required: false
          schema:
            type: string
            enum:
              - created_at
        - name: orderDirection
          description: '"asc" | "desc" (default: "desc")'
          in: query
          required: false
          schema:
            type: string
            enum:
              - asc
              - desc
        - name: statuses
          description: 'filter by status: "active", "closed", "pending"'
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: programType
          description: >-
            filter by program type (optional, e.g. "liquidityProgram",
            "volumeProgram")
          in: query
          required: false
          schema:
            type: string
        - name: query
          description: case-insensitive substring match on market_slug
          in: query
          required: false
          schema:
            type: string
        - name: instrumentStates
          description: filter by instrument lifecycle state (empty = no filter)
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
              enum:
                - INSTRUMENT_STATE_OPEN
                - INSTRUMENT_STATE_PREOPEN
                - INSTRUMENT_STATE_SUSPENDED
                - INSTRUMENT_STATE_EXPIRED
                - INSTRUMENT_STATE_TERMINATED
                - INSTRUMENT_STATE_HALTED
                - INSTRUMENT_STATE_MATCH_AND_CLOSE_AUCTION
                - INSTRUMENT_STATE_PENDING
        - name: category
          description: filter by instrument metadata "event_category" (exact match)
          in: query
          required: false
          schema:
            type: string
        - name: subcategory
          description: filter by instrument metadata "event_subcategory" (exact match)
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
                $ref: '#/components/schemas/v1ListIncentivesResponse'
components:
  schemas:
    v1ListIncentivesResponse:
      type: object
      properties:
        programs:
          type: array
          items:
            $ref: '#/components/schemas/v1IncentiveProgram'
          description: Incentive programs grouped by market
        nextPageToken:
          type: string
          description: Pagination token for next page. Empty if no more results
    v1IncentiveProgram:
      type: object
      properties:
        marketSlug:
          type: string
          description: Market identifier
        timePeriods:
          type: array
          items:
            $ref: '#/components/schemas/v1TimePeriod'
          description: Incentive time periods for this market
        instrumentState:
          $ref: '#/components/schemas/v1InstrumentState'
        category:
          type: string
          title: instrument metadata "event_category"
        subcategory:
          type: string
          title: instrument metadata "event_subcategory"
        eventStartTime:
          type: string
          title: instrument metadata "event_start_time" (ISO 8601 string)
        instrumentProduct:
          type: string
          title: instrument metadata "instrument_product"
      description: IncentiveProgram groups incentive time periods for a single market.
    v1TimePeriod:
      type: object
      properties:
        programId:
          type: string
          title: e.g. "aec-cbb-smu-miaoh-2026-03-18:mm_live"
          description: 'Unique identifier for this program period. Example: `nba_t1_ml_live`'
        programType:
          type: string
          title: '"liquidityProgram"'
          description: 'Type of incentive program. Example: `liquidityProgram`'
        start:
          type: string
          title: ISO 8601 timestamp
          description: ISO 8601 start timestamp for this period
        end:
          type: string
          title: ISO 8601 timestamp, omitted when the end is unknown
          nullable: true
          description: >-
            ISO 8601 end timestamp for this period. Omitted when the final end
            time is not known yet, such as an in-progress live game.
        rewardPool:
          type: number
          format: double
          description: Total reward pool for this period in USD
        status:
          type: string
          title: '"active" | "closed" | "pending"'
          enum:
            - active
            - closed
            - pending
          description: Current status of this period
        discountFactor:
          type: number
          format: double
          nullable: true
          description: >-
            Discount factor for scoring — controls how much orders further from
            the best price are penalized
        targetSize:
          type: integer
          format: int32
          title: liquidity programs only
          nullable: true
          description: >-
            Minimum aggregate resting order size on a side of the book for that
            side to qualify
        maxSpread:
          type: number
          format: double
          nullable: true
          description: >-
            Liquidity programs only: optional half-width in price dollars (0.035
            = 3.5¢ from mid). Each side's size-adjusted price is the price level
            at which that side of the book, walked from the best price outward,
            reaches targetSize. Where set, a second pays only when both sides
            reach targetSize and each size-adjusted price sits no more than
            maxSpread from the midpoint between the two (so they are at most 2 ×
            maxSpread apart); otherwise nobody is paid for that second. Omitted
            when the program has no Max Spread; a 0 is never sent.
        period:
          type: string
          title: e.g. "live", "day_of", "early"
          description: 'Reward period type. Example: `early`, `day_of`, `live`'
        createdAt:
          type: string
          title: ISO 8601 timestamp
          description: ISO 8601 timestamp when the program was created
        minTakerNotional:
          type: integer
          format: int32
          title: volume programs only
          nullable: true
      description: TimePeriod describes a specific incentive program within a time window.
    v1InstrumentState:
      type: string
      enum:
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