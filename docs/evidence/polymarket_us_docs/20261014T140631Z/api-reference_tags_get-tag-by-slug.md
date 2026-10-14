> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Tag By Slug

> Get a tag by its slug



## OpenAPI

````yaml /api-reference/oapi-schemas/tags-schema.json get /v2/tags/slug/{slug}
openapi: 3.0.3
info:
  title: protos/gateway/tags/v2/tags.proto
  version: 1.0.0
servers:
  - url: https://gateway.polymarket.us
    description: Production server
security: []
tags:
  - name: TagsV2Service
paths:
  /v2/tags/slug/{slug}:
    get:
      tags:
        - Tags
      summary: Get Tag By Slug
      description: Get a tag by its slug
      operationId: TagsV2Service_GetTagBySlug
      parameters:
        - name: slug
          description: Tag slug to retrieve
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: A successful response.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gateway.tags.v1.GetTagBySlugResponse'
components:
  schemas:
    gateway.tags.v1.GetTagBySlugResponse:
      type: object
      properties:
        tag:
          $ref: '#/components/schemas/gateway.tags.v1.Tag'
    gateway.tags.v1.Tag:
      type: object
      properties:
        id:
          type: string
          description: Unique tag identifier
        label:
          type: string
          description: Tag label
          nullable: true
        slug:
          type: string
          description: Tag slug for URL
          nullable: true
        createdAt:
          type: string
          description: Creation timestamp
          nullable: true
        updatedAt:
          type: string
          description: Last update timestamp
          nullable: true
        image:
          type: string
          description: Tag image URL
          nullable: true
        tradable:
          type: boolean
          description: Whether the tag is tradable
          nullable: true
        league:
          $ref: '#/components/schemas/gateway.tags.v1.TagLeague'
        sport:
          $ref: '#/components/schemas/gateway.tags.v1.TagSport'
        parentId:
          type: integer
          format: int32
          description: Parent tag ID
          nullable: true
        subtags:
          type: array
          items:
            type: object
            description: Nested object (recursive)
          description: Child subtags
    gateway.tags.v1.TagLeague:
      type: object
      properties:
        id:
          type: integer
          format: int32
        name:
          type: string
        sportId:
          type: integer
          format: int32
        tagId:
          type: integer
          format: int32
          nullable: true
        image:
          type: string
          nullable: true
        resolution:
          type: string
          nullable: true
        ordering:
          type: string
          nullable: true
        activeSeriesId:
          type: integer
          format: int32
          nullable: true
        isOperational:
          type: boolean
          nullable: true
        automaticResolution:
          type: boolean
          nullable: true
        createdAt:
          type: string
          nullable: true
        slug:
          type: string
        abbreviation:
          type: string
          nullable: true
    gateway.tags.v1.TagSport:
      type: object
      properties:
        id:
          type: integer
          format: int32
        name:
          type: string
        tagId:
          type: integer
          format: int32
          nullable: true
        createdAt:
          type: string
          nullable: true
        slug:
          type: string
        image:
          type: string
          nullable: true

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.