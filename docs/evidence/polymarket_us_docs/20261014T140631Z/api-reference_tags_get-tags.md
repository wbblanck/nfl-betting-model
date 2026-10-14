> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Tags

> Get ranked tags with optional filtering



## OpenAPI

````yaml /api-reference/oapi-schemas/tags-schema.json get /v2/tags
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
  /v2/tags:
    get:
      tags:
        - Tags
      summary: Get Tags
      description: Get ranked tags with optional filtering
      operationId: TagsV2Service_GetTags
      parameters:
        - name: limit
          description: Pagination limit
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: offset
          description: Pagination offset
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: orderBy
          description: Pagination order
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: orderDirection
          description: Pagination order direction
          in: query
          required: false
          schema:
            type: string
        - name: slug
          description: Tag slug to filter by
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: string
        - name: ids
          description: List of tag IDs to filter by
          in: query
          required: false
          explode: true
          schema:
            type: array
            items:
              type: integer
              format: int32
        - name: parentId
          description: Filter by parent tag ID. Ignored if parent_slug is provided.
          in: query
          required: false
          schema:
            type: integer
            format: int32
        - name: parentSlug
          description: >-
            Filter by parent tag slug. Takes priority over parent_id if both are
            provided.
          in: query
          required: false
          schema:
            type: string
        - name: query
          description: Case-insensitive substring match on tag label.
          in: query
          required: false
          schema:
            type: string
      responses:
        '200':
          description: List of tags
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/gateway.tags.v1.GetTagsResponse'
        '400':
          description: Bad request - invalid tag data
          content:
            application/json:
              schema: {}
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
    gateway.tags.v1.GetTagsResponse:
      type: object
      properties:
        tags:
          type: array
          items:
            $ref: '#/components/schemas/gateway.tags.v1.Tag'
          description: List of tags
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