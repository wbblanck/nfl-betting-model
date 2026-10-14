> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Sports

> Fetch sports data



## OpenAPI

````yaml /api-reference/oapi-schemas/sports-legacy-schema.json get /v1/sports
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
  /v1/sports:
    get:
      tags:
        - Sports
      summary: Get Sports
      description: Fetch sports data
      operationId: SportsService_GetSports
      responses:
        '200':
          description: Sports details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gateway.sports.v1.GetSportsResponse'
        '500':
          description: Internal server error
          content:
            application/json:
              schema: {}
components:
  schemas:
    gateway.sports.v1.GetSportsResponse:
      type: object
      properties:
        sports:
          type: array
          items:
            $ref: '#/components/schemas/gateway.sports.v1.Sport'
    gateway.sports.v1.Sport:
      type: object
      properties:
        sport:
          type: string
          description: The name of the sport
        image:
          type: string
          description: The image of the sport
        resolution:
          type: string
          description: The resolution of the sport
        ordering:
          type: string
          description: The ordering of the sport
        tags:
          type: string
          description: The tags of the sport
        series:
          type: string
          description: Series
        isOperational:
          type: boolean
          description: Whether the sport is operational
        automaticResolution:
          type: boolean
          description: Whether the sport has automatic resolution
        defaultJerseyImage:
          type: string
          description: Default jersey image URL for the parent sport
          nullable: true

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.