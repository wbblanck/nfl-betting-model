> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get All Leagues

> Retrieve leagues with pagination (max 50 per page)



## OpenAPI

````yaml /api-reference/oapi-schemas/sports-schema.json get /v2/leagues
openapi: 3.0.3
info:
  title: protos/gateway/sports/v2/sports.proto
  version: 1.0.0
servers:
  - url: https://gateway.polymarket.us
    description: Production server
security: []
tags:
  - name: SportsV2Service
paths:
  /v2/leagues:
    get:
      tags:
        - Sports
      summary: Get All Leagues
      description: Retrieve leagues with pagination (max 50 per page)
      operationId: SportsV2Service_GetLeagues
      parameters:
        - name: limit
          description: Pagination limit (max 50, default 50)
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: offset
          description: Pagination offset (default 0)
          in: query
          required: false
          schema:
            type: integer
            format: int32
      responses:
        '200':
          description: List of leagues
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gateway.sports.v2.GetLeaguesResponse'
        '500':
          description: Internal server error
          content:
            application/json:
              schema: {}
components:
  schemas:
    gateway.sports.v2.GetLeaguesResponse:
      type: object
      properties:
        leagues:
          type: array
          items:
            $ref: '#/components/schemas/gateway.sports.v2.League'
          description: List of leagues
    gateway.sports.v2.League:
      type: object
      properties:
        name:
          type: string
          description: League name (e.g., NFL, NBA)
        slug:
          type: string
          description: League slug
        image:
          type: string
          description: League image URL
          nullable: true
        isOperational:
          type: boolean
          description: Whether the league is operational
          nullable: true
        id:
          type: integer
          format: int32
          description: League ID
        sportId:
          type: integer
          format: int32
          description: Parent sport ID
        tagId:
          type: integer
          format: int32
          description: Associated tag ID
          nullable: true
        resolution:
          type: string
          description: League resolution
          nullable: true
        ordering:
          type: string
          description: League ordering
          nullable: true
        activeSeriesId:
          type: integer
          format: int32
          description: Active series ID
          nullable: true
        createdAt:
          type: string
          description: Creation timestamp
          nullable: true
        abbreviation:
          type: string
          description: League abbreviation
          nullable: true
      description: Consumer-facing league representation

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.