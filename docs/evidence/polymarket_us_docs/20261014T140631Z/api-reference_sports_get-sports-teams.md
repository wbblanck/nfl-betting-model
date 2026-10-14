> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Sports Teams

> Fetch sports teams data for enriching sports events



## OpenAPI

````yaml /api-reference/oapi-schemas/sports-legacy-schema.json get /v1/sports/teams
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
  /v1/sports/teams:
    get:
      tags:
        - Sports
      summary: Get Sports Teams
      description: Fetch sports teams data for enriching sports events
      operationId: SportsService_GetSportsTeams
      parameters:
        - name: limit
          description: Maximum number of teams to return
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: offset
          description: Number of teams to skip for pagination
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: orderBy
          description: Order by field
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: orderDirection
          description: Order direction
          in: query
          required: false
          schema:
            type: string
        - name: filters.league
          description: Filter by league
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
        - name: filters.abbreviation
          description: Filter by abbreviation
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: filters.id
          description: Team ids
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: integer
              format: int32
      responses:
        '200':
          description: List of sports teams
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gateway.sports.v1.GetSportsTeamsResponse'
        '401':
          description: Unauthorized - invalid or missing authentication token
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
    gateway.sports.v1.GetSportsTeamsResponse:
      type: object
      properties:
        teams:
          type: array
          items:
            $ref: '#/components/schemas/gateway.sports.v1.SportsTeam'
    gateway.sports.v1.SportsTeam:
      type: object
      properties:
        id:
          type: string
          format: int64
          description: Sports team identifier
        name:
          type: string
          description: Sports team name
        abbreviation:
          type: string
          description: Sports team abbreviation
        updatedBy:
          type: string
          format: int64
          description: Sports team updated by
        createdAt:
          type: string
          description: Sports team created at
        updatedAt:
          type: string
          description: Sports team updated at
        league:
          type: string
          description: Sports team league
        record:
          type: string
          description: Sports team record
        logo:
          type: string
          description: Sports team logo
        alias:
          type: string
          description: Sports team alias
        homeIcon:
          type: string
          description: Sports team home icon
          nullable: true
        awayIcon:
          type: string
          description: Sports team away icon
          nullable: true
        colorPrimary:
          type: string
          description: Sports team color primary
          nullable: true
        safeName:
          type: string
          description: Sports team alias
        providerId:
          type: string
          format: int64
          description: Provider id
          nullable: true
        ordering:
          type: string
          description: Away or home
          nullable: true
        longIcon:
          type: string
          description: Sports team long icon
          nullable: true
        shortIcon:
          type: string
          description: Sports team short icon
          nullable: true
        displayAbbreviation:
          type: string
          description: Sports team abbreviation to be displayed
          nullable: true
        ranking:
          type: string
          format: int64
          description: Team ranking
          nullable: true
        conference:
          type: string
          description: Team conference
          nullable: true
        providerIds:
          type: array
          items:
            $ref: '#/components/schemas/gateway.sports.v1.SportsTeamProvider'
          description: Team providers
        longIconDark:
          type: string
          description: Sports team long icon dark
          nullable: true
        shortIconDark:
          type: string
          description: Sports team short icon dark
          nullable: true
        colorSecondary:
          type: string
          description: Sports team color secondary (light mode)
          nullable: true
        colorDarkPrimary:
          type: string
          description: Sports team color primary (dark mode)
          nullable: true
        colorDarkSecondary:
          type: string
          description: Sports team color secondary (dark mode)
          nullable: true
      description: Sports team information including name, logo, stats, and roster details
    gateway.sports.v1.SportsTeamProvider:
      type: object
      properties:
        provider:
          $ref: '#/components/schemas/gateway.sports.v1.Provider'
        providerId:
          type: string
          description: The provider id
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