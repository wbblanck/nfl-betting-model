> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Sports Players

> Fetch sports players, filterable by abbreviation, name, id, team, or provider reference



## OpenAPI

````yaml /api-reference/oapi-schemas/sports-legacy-schema.json get /v1/sports/players
openapi: 3.0.3
info:
  title: protos/gateway/sports/v1/sports.proto
  version: 1.0.0
servers:
  - url: https://gateway.polymarket.us
    description: Production server
security: []
tags:
  - name: SportsService
paths:
  /v1/sports/players:
    get:
      tags:
        - Sports
      summary: Get Sports Players
      description: >-
        Fetch sports players, filterable by abbreviation, name, id, team, or
        provider reference
      operationId: SportsService_GetSportsPlayers
      parameters:
        - name: limit
          description: Maximum number of players to return
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: offset
          description: Number of players to skip for pagination
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: filters.abbreviation
          description: Filter by abbreviation
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: filters.name
          description: Filter by name
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: filters.id
          description: Filter by player id
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
              format: int64
        - name: filters.teamId
          description: Filter by team id
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
              format: int64
        - name: filters.provider
          description: Filter by data provider; combine with provider_player_id
          in: query
          required: false
          schema:
            type: string
            enum:
              - PROVIDER_SPORTSDATAIO
              - PROVIDER_SPORTRADAR
              - PROVIDER_OPTICODDS
              - PROVIDER_PANDASCORE
              - PROVIDER_INFRONT
              - PROVIDER_ENETPULSE
              - PROVIDER_UFC
              - PROVIDER_ODDSPAPI
              - PROVIDER_BETER
              - PROVIDER_CHAMPION_DATA
        - name: filters.providerPlayerId
          description: Filter by provider player id; requires provider
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: filters.league
          description: >-
            Restrict to players on teams in this league; only honored with a
            provider filter
          in: query
          required: false
          schema:
            type: string
      responses:
        '200':
          description: List of sports players
          content:
            application/json:
              schema:
                $ref: >-
                  #/components/schemas/gateway.sports.v1.GetSportsPlayersResponse
        '500':
          description: Internal server error
          content:
            application/json:
              schema: {}
components:
  schemas:
    gateway.sports.v1.GetSportsPlayersResponse:
      type: object
      properties:
        players:
          type: array
          items:
            $ref: '#/components/schemas/gateway.sports.v1.SportsPlayer'
          description: List of players
    gateway.sports.v1.SportsPlayer:
      type: object
      properties:
        id:
          type: string
          format: int64
          description: Player identifier
        name:
          type: string
          description: Player name
        abbreviation:
          type: string
          description: Player abbreviation
        teamId:
          type: string
          format: int64
          description: Player team id
          nullable: true
        image:
          type: string
          description: Player image URL
          nullable: true
        providerIds:
          type: array
          items:
            $ref: '#/components/schemas/gateway.sports.v1.SportsPlayerProvider'
          description: Player provider references
        darkImage:
          type: string
          description: Player dark-mode image URL; empty when unavailable
        jerseyNumber:
          type: integer
          format: int32
          description: Player jersey number; absent when unavailable
          nullable: true
        jerseyImage:
          type: string
          description: Player jersey image URL; empty when unavailable
        jerseyDarkImage:
          type: string
          description: Player dark-mode jersey image URL; empty when unavailable
      description: Sports player information
    gateway.sports.v1.SportsPlayerProvider:
      type: object
      properties:
        provider:
          $ref: '#/components/schemas/gateway.sports.v1.Provider'
        providerId:
          type: string
          description: The provider player id
    gateway.sports.v1.Provider:
      type: string
      enum:
        - PROVIDER_SPORTSDATAIO
        - PROVIDER_SPORTRADAR
        - PROVIDER_OPTICODDS
        - PROVIDER_PANDASCORE
        - PROVIDER_INFRONT
        - PROVIDER_ENETPULSE
        - PROVIDER_UFC
        - PROVIDER_ODDSPAPI
        - PROVIDER_BETER
        - PROVIDER_CHAMPION_DATA

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.