> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Your Incentive Earnings

> Returns rewards earned by the authenticated caller. Each entry sums all payouts for a single (market, date) pair, where date is in Eastern Time.



## OpenAPI

````yaml /api-reference/oapi-schemas/incentives-schema.json get /v1/incentives/earnings
openapi: 3.0.3
info:
  title: protos/gateway/incentives/v1/incentives.proto
  version: 1.0.0
servers:
  - url: https://api.polymarket.us
    description: Production server
security: []
tags:
  - name: IncentivesService
paths:
  /v1/incentives/earnings:
    get:
      tags:
        - Incentives
      summary: Get Your Incentive Earnings
      description: >-
        Returns rewards earned by the authenticated caller. Each entry sums all
        payouts for a single (market, date) pair, where date is in Eastern Time.
      operationId: IncentivesService_GetIncentivesEarned
      parameters:
        - name: start_date
          description: >-
            Start date filter (`YYYY-MM-DD`). Defaults to the program launch
            date.
          in: query
          required: false
          schema:
            type: string
        - name: end_date
          description: End date filter (`YYYY-MM-DD`). Omit for through-today.
          in: query
          required: false
          schema:
            type: string
        - name: market_slug
          description: Filter by market slug.
          in: query
          required: false
          schema:
            type: string
        - name: program_type
          description: Filter by program type (e.g. `liquidityProgram`).
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
                $ref: >-
                  #/components/schemas/gateway.incentives.v1.GetIncentivesEarnedResponse
components:
  schemas:
    gateway.incentives.v1.GetIncentivesEarnedResponse:
      type: object
      properties:
        rewards:
          type: array
          items:
            $ref: '#/components/schemas/gateway.incentives.v1.UserReward'
    gateway.incentives.v1.UserReward:
      type: object
      properties:
        reward:
          type: number
          format: double
        programType:
          type: string
        marketSlug:
          type: string
        date:
          type: string
        status:
          type: string

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.