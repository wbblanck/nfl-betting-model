> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get League By Slug

> Retrieve a league by its slug



## OpenAPI

````yaml /api-reference/oapi-schemas/sports-schema.json get /v2/leagues/{slug}
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
  /v2/leagues/{slug}:
    get:
      tags:
        - Sports
      summary: Get League By Slug
      description: Retrieve a league by its slug
      operationId: SportsV2Service_GetLeagueBySlug
      parameters:
        - name: slug
          description: League slug
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: League
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gateway.sports.v2.GetLeagueBySlugResponse'
        '404':
          description: League not found
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
    gateway.sports.v2.GetLeagueBySlugResponse:
      type: object
      properties:
        league:
          $ref: '#/components/schemas/gateway.sports.v2.League'
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