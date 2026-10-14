> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Event By Partner External ID

> Resolve a partner external event ID (e.g. OpticOdds fixture ID) to the internal event and its mapped market sides



## OpenAPI

````yaml /api-reference/oapi-schemas/events-schema.json get /v1/partners/{partnerKey}/events/{externalId}
openapi: 3.0.3
info:
  title: protos/gateway/events/v1/events.proto
  version: 1.0.0
servers:
  - url: https://gateway.polymarket.us
    description: Production server
security: []
tags:
  - name: EventsService
paths:
  /v1/partners/{partnerKey}/events/{externalId}:
    get:
      tags:
        - Partners
      summary: Get Event By Partner External ID
      description: >-
        Resolve a partner external event ID (e.g. OpticOdds fixture ID) to the
        internal event and its mapped market sides
      operationId: EventsService_GetEventByPartnerExternalID
      parameters:
        - name: partnerKey
          description: Partner slug (e.g. opticodds)
          in: path
          required: true
          schema:
            type: string
        - name: externalId
          description: Partner external event ID (e.g. OpticOdds fixture ID)
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Event details with mapped market sides
          content:
            application/json:
              schema:
                $ref: >-
                  #/components/schemas/gateway.events.v1.GetEventByPartnerExternalIDResponse
        '404':
          description: Partner event link not found
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
    gateway.events.v1.GetEventByPartnerExternalIDResponse:
      type: object
      properties:
        event:
          $ref: '#/components/schemas/gateway.market.v1.Event'
        mappedMarketSides:
          type: array
          items:
            $ref: '#/components/schemas/gateway.events.v1.MappedMarketSide'
          description: Partner-linked market sides for this event
    gateway.market.v1.Event:
      type: object
      properties:
        id:
          type: string
          description: Unique event identifier
        ticker:
          type: string
          description: Event ticker symbol
          nullable: true
        slug:
          type: string
          description: Event slug for URL
          nullable: true
        title:
          type: string
          description: Event title
          nullable: true
        subtitle:
          type: string
          description: Event subtitle
          nullable: true
        description:
          type: string
          description: Event description
          nullable: true
        resolutionSource:
          type: string
          description: Source for event resolution
          nullable: true
        startDate:
          type: string
          description: Event start date
          nullable: true
        creationDate:
          type: string
          description: Event creation date
          nullable: true
        endDate:
          type: string
          description: Event end date
          nullable: true
        image:
          type: string
          description: Event image URL
          nullable: true
        imageDisplayType:
          $ref: '#/components/schemas/gateway.market.v1.ImageDisplayType'
        active:
          type: boolean
          description: Whether event is active
          nullable: true
        closed:
          type: boolean
          description: Whether event is closed
          nullable: true
        archived:
          type: boolean
          description: Whether event is archived
          nullable: true
        liquidity:
          type: number
          format: decimal
          description: Event liquidity
          nullable: true
        volume:
          type: number
          format: decimal
          description: Event volume
          nullable: true
        openInterest:
          type: number
          format: decimal
          description: Open interest
          nullable: true
        category:
          type: string
          description: Event category
          nullable: true
        subcategory:
          type: string
          description: Event subcategory
          nullable: true
        createdAt:
          type: string
          description: Creation timestamp
          nullable: true
        updatedAt:
          type: string
          description: Last update timestamp
          nullable: true
        volume24hr:
          type: number
          format: decimal
          description: 24-hour volume
          nullable: true
        volume1wk:
          type: number
          format: decimal
          description: One week volume
          nullable: true
        volume1mo:
          type: number
          format: decimal
          description: One month volume
          nullable: true
        volume1yr:
          type: number
          format: decimal
          description: One year volume
          nullable: true
        closedTime:
          type: string
          description: Event close time
          nullable: true
        eventDate:
          type: string
          description: Event date
          nullable: true
        startTime:
          type: string
          description: Event start time
          nullable: true
        seriesSlug:
          type: string
          description: Series slug
          nullable: true
        score:
          type: string
          description: Event score
          nullable: true
        elapsed:
          type: string
          description: Elapsed time
          nullable: true
        period:
          type: string
          description: Event period
          nullable: true
        live:
          type: boolean
          description: Whether event is live
          nullable: true
        ended:
          type: boolean
          description: Whether event has ended
          nullable: true
        finishedTimestamp:
          type: string
          description: Finished timestamp
          nullable: true
        featuredOrder:
          type: integer
          format: int32
          description: Featured order
          nullable: true
        markets:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.Market'
          description: Associated markets
        gameId:
          type: integer
          format: int32
          description: ID taken from our sports provider
          nullable: true
        rescheduledFromGameId:
          type: integer
          format: int32
          description: Rescheduled ID taken from our sports provider
          nullable: true
        sportradarGameId:
          type: string
          description: Sportradar game ID
          nullable: true
        eventState:
          $ref: '#/components/schemas/gateway.market.v1.EventState'
        hidden:
          type: boolean
          description: Whether event is hidden
          nullable: true
        tags:
          type: array
          items:
            $ref: '#/components/schemas/gateway.tags.v1.Tag'
          description: Associated tags
        teams:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.Team'
          description: Associated teams
        metadata:
          $ref: '#/components/schemas/gateway.market.v1.EventMetadata'
        sortType:
          type: string
          description: Sort type for ordering markets within event
          nullable: true
        marketGroups:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.EventMarketGroup'
          description: >-
            Flat list of market groups forming a hierarchy via parent_id (only
            when groups=true)
        primaryTag:
          $ref: '#/components/schemas/gateway.tags.v1.Tag'
        secondaryTag:
          $ref: '#/components/schemas/gateway.tags.v1.Tag'
        primaryTagSlug:
          type: string
          description: >-
            Raw upstream primary tag slug override (admin-only; omitted on
            public reads)
          nullable: true
        secondaryTagSlug:
          type: string
          description: >-
            Raw upstream secondary tag slug override (admin-only; omitted on
            public reads)
          nullable: true
        livestreamUrl:
          type: string
          description: Livestream URL for the event
          nullable: true
        streamProvider:
          type: string
          description: >-
            Stream provider identifier (e.g. "beter") signaling the event has a
            stream resolvable via the event stream endpoint; empty means none
        streamRequiresAuth:
          type: boolean
          description: >-
            When true, the event stream endpoint only resolves for authenticated
            requests (the provider signs manifests per viewer identity);
            anonymous requests fail. Always false when stream_provider is empty.
        featureAvailability:
          $ref: '#/components/schemas/gateway.market.v1.EventFeatureAvailability'
        combos:
          $ref: '#/components/schemas/gateway.market.v1.EventCombos'
        marketCounts:
          $ref: '#/components/schemas/gateway.market.v1.EventMarketCounts'
      description: Event information and configuration
    gateway.events.v1.MappedMarketSide:
      type: object
      properties:
        marketSideId:
          type: integer
          format: int32
        marketId:
          type: integer
          format: int32
        eventId:
          type: integer
          format: int32
        externalEventId:
          type: string
        externalMarketType:
          type: string
        externalNormalizedSelection:
          type: string
        externalSelectionLine:
          type: string
        externalPoints:
          type: string
    gateway.market.v1.ImageDisplayType:
      type: string
      enum:
        - IMAGE_DISPLAY_TYPE_HEADSHOT
        - IMAGE_DISPLAY_TYPE_LOGO
        - IMAGE_DISPLAY_TYPE_FLAG
        - IMAGE_DISPLAY_TYPE_ARTWORK
    gateway.market.v1.Market:
      type: object
      properties:
        id:
          type: string
          description: Unique market identifier
        question:
          type: string
          description: Market question
          nullable: true
        slug:
          type: string
          description: Market slug for URL
          nullable: true
        endDate:
          type: string
          description: Market end date
          nullable: true
        category:
          type: string
          description: Market category
          nullable: true
        startDate:
          type: string
          description: Market start date
          nullable: true
        image:
          type: string
          description: Market image URL
          nullable: true
        imageDisplayType:
          $ref: '#/components/schemas/gateway.market.v1.ImageDisplayType'
        description:
          type: string
          description: Market description
          nullable: true
        active:
          type: boolean
          description: Whether market is active
          nullable: true
        marketType:
          type: string
          description: 'Type of market (deprecated). Options: moneyline, spreads, totals'
          nullable: true
          deprecated: true
        closed:
          type: boolean
          description: Whether market is closed
          nullable: true
        createdAt:
          type: string
          description: Creation timestamp
          nullable: true
        updatedAt:
          type: string
          description: Last update timestamp
          nullable: true
        archived:
          type: boolean
          description: Whether market is archived
          nullable: true
          deprecated: true
        orderPriceMinTickSize:
          type: number
          format: decimal
          description: Minimum tick size for order price
          nullable: true
        gameStartTime:
          type: string
          description: Game start time
          nullable: true
          deprecated: true
        manualActivation:
          type: boolean
          description: Whether manual activation is required
          nullable: true
          deprecated: true
        sportsMarketType:
          type: string
          description: Sports market type
          nullable: true
        line:
          type: number
          format: decimal
          description: Line value
          nullable: true
        marketSides:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.MarketSide'
          description: Market sides
        outcomes:
          type: string
          description: Outcomes JSON
          nullable: true
          deprecated: true
        outcomePrices:
          type: string
          description: Outcome prices JSON
          nullable: true
          deprecated: true
        ep3Status:
          type: string
          description: Raw upstream EP3 instrument state (deprecated). Use status.
          nullable: true
        status:
          $ref: '#/components/schemas/gateway.market.v1.MarketStatus'
        assetPriceTerms:
          allOf:
            - $ref: '#/components/schemas/gateway.market.v1.AssetPriceTerms'
          description: >-
            Typed terms of an automated crypto price market. Null on every other
            market, including the hand-listed year-end crypto markets.
        sportsMarketTypeV2:
          allOf:
            - $ref: '#/components/schemas/gateway.market.v1.SportsMarketType'
          deprecated: true
        hidden:
          type: boolean
          description: Whether market is hidden
          nullable: true
        tags:
          type: array
          items:
            $ref: '#/components/schemas/gateway.tags.v1.Tag'
          description: Associated tags
        title:
          type: string
          description: Market title
          nullable: true
        subtitle:
          type: string
          description: Market subtitle
          nullable: true
        color:
          type: string
          description: Market color
          nullable: true
        darkColor:
          type: string
          description: Market dark mode color
          nullable: true
        subjectId:
          type: integer
          format: int32
          description: Subject ID
          nullable: true
        subject:
          $ref: '#/components/schemas/gateway.market.v1.Subject'
        feeCoefficient:
          type: number
          format: decimal
          description: Fee coefficient
          nullable: true
        spreadTotalSuffix:
          type: string
          description: Spread/total suffix for UI display (e.g. points, goals, runs)
          nullable: true
        sortOrder:
          type: integer
          format: int32
          description: Sort order for market within event
          nullable: true
        bestBidQuote:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        bestAskQuote:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        metadata:
          type: object
          description: >-
            Opaque metadata object — internal-use only, shape is not part of the
            public contract
          nullable: true
        titleShort:
          type: string
          description: >-
            Compact display title computed at serialization time (e.g. 'DET -5.5
            F5', 'Over 5.5 F5'). Falls back to title.
          nullable: true
        ep3SyncedAt:
          type: string
          description: Timestamp when this market was last synced from EP3
          nullable: true
        minimumTradeQty:
          type: number
          format: decimal
          description: >-
            Minimum order quantity in contracts (e.g. 0.01 = 1% of a contract,
            1.0 = one whole contract).
          nullable: true
        volume:
          type: number
          format: decimal
          description: Market volume (lifetime, in shares)
          nullable: true
        volume24hr:
          type: number
          format: decimal
          description: 24-hour market volume (in shares)
          nullable: true
        volume1wk:
          type: number
          format: decimal
          description: One week market volume (in shares)
          nullable: true
        volume1mo:
          type: number
          format: decimal
          description: One month market volume (in shares)
          nullable: true
        volume1yr:
          type: number
          format: decimal
          description: One year market volume (in shares)
          nullable: true
        rulesDisclaimer:
          type: string
          description: >-
            Short 'understanding the rules' disclaimer for this market type,
            computed at serialization time. Omitted when the market's
            sports_market_type has no disclaimer.
          nullable: true
        rulesDisclaimerPopup:
          type: boolean
          description: >-
            When true, clients should surface rules_disclaimer as a popup sheet
            the user acknowledges before buying, rather than inline. Only set
            when rules_disclaimer is present.
          nullable: true
        comboEnabled:
          type: boolean
          description: Whether this market is combo-enabled
          nullable: true
      description: Market information and configuration
    gateway.market.v1.EventState:
      type: object
      properties:
        id:
          type: integer
          format: int32
        gameId:
          type: integer
          format: int32
          nullable: true
        sportradarGameId:
          type: string
          nullable: true
        type:
          type: string
        createdAt:
          type: string
          format: date-time
          nullable: true
        updatedAt:
          type: string
          format: date-time
          nullable: true
        score:
          type: string
          nullable: true
        elapsed:
          type: string
          nullable: true
        period:
          type: string
          nullable: true
        live:
          type: boolean
          nullable: true
        ended:
          type: boolean
          nullable: true
        finishedTimestamp:
          type: string
          format: date-time
          nullable: true
        footballState:
          $ref: '#/components/schemas/gateway.market.v1.FootballState'
        ufcState:
          $ref: '#/components/schemas/gateway.market.v1.UFCState'
        tennisState:
          $ref: '#/components/schemas/gateway.market.v1.TennisState'
        baseballState:
          $ref: '#/components/schemas/gateway.market.v1.BaseballState'
        cricketState:
          $ref: '#/components/schemas/gateway.market.v1.CricketState'
        soccerState:
          $ref: '#/components/schemas/gateway.market.v1.SoccerState'
        mainSpreadLine:
          type: number
          format: double
          description: Main spread line
          title: Lines
          nullable: true
        mainTotalLine:
          type: number
          format: double
          description: Main total line
          nullable: true
        marketGroupStats:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.MarketGroupStat'
          description: Per-market-group current line and count
        periodScores:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.PeriodScore'
          description: >-
            Per-period scoring lines, ordered by play order, regulation before
            overtime. Not populated for cricket, which uses CricketState.innings
        eventId:
          type: integer
          format: int32
          description: ID of the event this state belongs to
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
        hub:
          $ref: '#/components/schemas/gateway.hubs.v1.Hub'
    gateway.market.v1.Team:
      type: object
      properties:
        id:
          type: integer
          format: int32
        name:
          type: string
        abbreviation:
          type: string
        league:
          type: string
        record:
          type: string
        logo:
          type: string
        alias:
          type: string
        safeName:
          type: string
        homeIcon:
          type: string
          nullable: true
        awayIcon:
          type: string
          nullable: true
        colorPrimary:
          type: string
          nullable: true
        providerId:
          type: integer
          format: int32
          nullable: true
        ordering:
          type: string
          nullable: true
        longIcon:
          type: string
          nullable: true
        shortIcon:
          type: string
          nullable: true
        displayAbbreviation:
          type: string
          nullable: true
        ranking:
          type: string
          format: int64
          nullable: true
        conference:
          type: string
          nullable: true
        providerIds:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.SportsTeamProvider'
        longIconDark:
          type: string
          nullable: true
        shortIconDark:
          type: string
          nullable: true
        color:
          $ref: '#/components/schemas/gateway.market.v1.ResolvedColor'
        imageDisplayType:
          $ref: '#/components/schemas/gateway.market.v1.ImageDisplayType'
    gateway.market.v1.EventMetadata:
      type: object
      properties:
        gameState:
          $ref: '#/components/schemas/gateway.market.v1.EventState'
        latestGameUpdate:
          $ref: '#/components/schemas/gateway.market.v1.GameUpdate'
    gateway.market.v1.EventMarketGroup:
      type: object
      properties:
        id:
          type: string
          description: >-
            Unique identifier for this group (path-based, e.g.
            'player-props/home-runs/yankees')
        title:
          type: string
          description: Display title for this group
        subtitle:
          type: string
          description: Optional display subtitle for this group
          nullable: true
        parentId:
          type: string
          description: ID of the parent group (null for root groups, which act as tabs)
          nullable: true
        order:
          type: integer
          format: int32
          description: Sort order among siblings with the same parent
        marketIds:
          type: array
          items:
            type: string
          description: Ordered market ID references into event.markets
        line:
          type: number
          format: decimal
          description: Line value for this group
          nullable: true
        current:
          type: number
          format: decimal
          description: Current line value
          nullable: true
        searchable:
          type: boolean
          description: Whether this group's markets are searchable
          nullable: true
        showAllThreshold:
          type: integer
          format: int32
          description: Number of markets to show before collapsing with a 'show all' button
          nullable: true
        showMarketImages:
          type: boolean
          description: Whether clients should render market images for this group
          nullable: true
        initialCollapsed:
          type: boolean
          description: >-
            Whether clients should render this group collapsed by default;
            unset/false means expanded
        live:
          type: boolean
          description: >-
            Whether clients should render a live indicator next to this group's
            title; unset/false means no indicator
    gateway.market.v1.EventFeatureAvailability:
      type: object
      properties:
        lineups:
          type: boolean
          description: Lineups are generally available for this event
        timeline:
          type: boolean
          description: >-
            Live timeline including statistics and play-by-play is generally
            available for this event
        stats:
          type: boolean
          description: Team statistics are generally available for this event
      description: Data surfaces available for this event
    gateway.market.v1.EventCombos:
      type: object
      properties:
        enabled:
          type: boolean
          description: Whether this event has at least one combo-enabled market
          nullable: true
        numMarkets:
          type: integer
          format: int32
          description: Number of open combo-enabled markets on this event
          nullable: true
        numSpreadsAndTotalsMarkets:
          type: integer
          format: int32
          description: Number of open combo-enabled spread and totals markets on this event
          nullable: true
    gateway.market.v1.EventMarketCounts:
      type: object
      properties:
        numMarkets:
          type: integer
          format: int32
          description: Number of open markets on this event
          nullable: true
        numSpreadsAndTotalsMarkets:
          type: integer
          format: int32
          description: Number of open spread and totals markets on this event
          nullable: true
    gateway.market.v1.MarketSide:
      type: object
      properties:
        id:
          type: string
          description: Market side ID
        marketSideType:
          $ref: '#/components/schemas/gateway.market.v1.MarketSideType'
        identifier:
          type: string
          description: Market side identifier
          nullable: true
        createdAt:
          type: string
          description: Creation timestamp
          nullable: true
        updatedAt:
          type: string
          description: Last update timestamp
          nullable: true
        description:
          type: string
          description: Market side description
          nullable: true
        price:
          type: string
          description: Market side price
          nullable: true
        marketId:
          type: integer
          format: int32
          description: Market ID
        long:
          type: boolean
          description: Whether market side is the long or short side of the market
          nullable: true
        teamId:
          type: integer
          format: int32
          description: Team ID
          nullable: true
        team:
          allOf:
            - $ref: '#/components/schemas/gateway.market.v1.Team'
          deprecated: true
        quote:
          $ref: '#/components/schemas/gateway.types.v1.Amount'
        tradable:
          type: boolean
          description: Whether this side can be traded
          nullable: true
      description: Market position information
    gateway.market.v1.MarketStatus:
      type: string
      enum:
        - MARKET_STATUS_UNSPECIFIED
        - MARKET_STATUS_OPEN
        - MARKET_STATUS_CLOSED
        - MARKET_STATUS_RESOLVING
        - MARKET_STATUS_RESOLVED
        - MARKET_STATUS_HALTED
      description: >-
        MarketStatus is the normalized trading lifecycle for a market, derived
        by the

        gateway. Values may grow; treat unrecognized values as

        MARKET_STATUS_UNSPECIFIED. Pre-trading upstream states have no
        counterpart

        here and read as MARKET_STATUS_UNSPECIFIED.

         - MARKET_STATUS_RESOLVING: Past expiry, final settlement not yet published — payouts are pending.
         - MARKET_STATUS_RESOLVED: Final settlement published; the outcome will not change.
    gateway.market.v1.AssetPriceTerms:
      type: object
      properties:
        marketType:
          $ref: '#/components/schemas/gateway.market.v1.AssetPriceMarketType'
        asset:
          $ref: '#/components/schemas/gateway.types.v1.AssetId'
        indexSymbol:
          type: string
          description: Reference index the market settles on, e.g. BRTI.
        horizon:
          type: string
          description: Supply-side horizon slug. Display and grouping only.
        windowStart:
          type: string
          format: date-time
          description: >-
            Start of the settlement window. Always set for UP_DOWN. Null when
            the market has no settlement window (ladders).
          nullable: true
        windowEnd:
          type: string
          format: date-time
          description: >-
            End of the measurement window and scheduled settlement instant. Set
            on every automated crypto family, including ABOVE_BELOW and RANGE
            ladders. Use this rather than endDate for the settlement time.
            ONE_TOUCH may settle Yes before this instant.
          nullable: true
        priceToBeat:
          allOf:
            - $ref: '#/components/schemas/gateway.types.v1.NullableAmount'
          description: >-
            Null until stamped a few seconds after windowStart, and on every
            market that is not UP_DOWN.
        strike:
          allOf:
            - $ref: '#/components/schemas/gateway.types.v1.NullableAmount'
          description: Null on every market that is not ABOVE_BELOW or ONE_TOUCH.
        rangeLower:
          allOf:
            - $ref: '#/components/schemas/gateway.types.v1.NullableAmount'
          description: >-
            Null on every market that is not a RANGE, and on the open side of a
            tail range.
        rangeUpper:
          allOf:
            - $ref: '#/components/schemas/gateway.types.v1.NullableAmount'
          description: >-
            Null on every market that is not a RANGE, and on the open side of a
            tail range.
        rangeKind:
          $ref: '#/components/schemas/gateway.market.v1.AssetPriceRangeKind'
        direction:
          $ref: '#/components/schemas/gateway.market.v1.AssetPriceDirection'
        settlementPrice:
          allOf:
            - $ref: '#/components/schemas/gateway.types.v1.NullableAmount'
          description: >-
            Null until resolved, and stays null on a ONE_TOUCH market that
            resolved No: no price was touched.
      description: >-
        Terms of a market settled against an external reference (index) price.
        Fields a market type does not use are null, never zero-filled. Prices
        are decimal strings exactly as the supply side stamped them.
      nullable: true
    gateway.market.v1.SportsMarketType:
      type: string
      enum:
        - SPORTS_MARKET_TYPE_MONEYLINE
        - SPORTS_MARKET_TYPE_SPREAD
        - SPORTS_MARKET_TYPE_TOTAL
        - SPORTS_MARKET_TYPE_PROP
        - SPORTS_MARKET_TYPE_FUTURE
        - SPORTS_MARKET_TYPE_DRAWABLE_OUTCOME
    gateway.market.v1.Subject:
      type: object
      properties:
        id:
          type: integer
          format: int32
          description: Subject ID
        name:
          type: string
          description: Subject name
        displayName:
          type: string
          description: Subject display name
          nullable: true
        description:
          type: string
          description: Subject description
          nullable: true
        subjectType:
          type: string
          description: Subject type (nominee, player, team, candidate, golf_player)
        image:
          type: string
          description: Subject image URL
          nullable: true
        color:
          type: string
          description: Subject color
          nullable: true
        darkColor:
          type: string
          description: Subject dark mode color
          nullable: true
        createdAt:
          type: string
          description: Creation timestamp
          nullable: true
        updatedAt:
          type: string
          description: Last update timestamp
          nullable: true
        slug:
          type: string
          description: Subject slug for URL
          nullable: true
      description: Subject information
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
    gateway.market.v1.FootballState:
      type: object
      properties:
        down:
          type: integer
          format: int32
          description: Deprecated, use drive_state.down
          nullable: true
        yard:
          type: integer
          format: int32
          description: Deprecated, use drive_state.yfd (yards to go)
          nullable: true
        possessionProviderId:
          type: string
          description: Deprecated, use drive_state.possession_team_id
          nullable: true
        driveState:
          $ref: '#/components/schemas/gateway.market.v1.FootballDriveState'
        timeouts:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.FootballTeamTimeouts'
    gateway.market.v1.UFCState:
      type: object
      properties:
        weightClass:
          type: string
          nullable: true
        cardSegment:
          type: string
          nullable: true
        eventLogo:
          type: string
          nullable: true
        rounds:
          type: integer
          format: int32
          nullable: true
        order:
          type: integer
          format: int32
          nullable: true
    gateway.market.v1.TennisState:
      type: object
      properties:
        tournamentName:
          type: string
          nullable: true
        round:
          type: string
          nullable: true
        servingTeamId:
          type: integer
          format: int32
          nullable: true
    gateway.market.v1.BaseballState:
      type: object
      properties:
        balls:
          type: integer
          format: int32
          nullable: true
        strikes:
          type: integer
          format: int32
          nullable: true
        outs:
          type: integer
          format: int32
          nullable: true
        onFirst:
          type: boolean
          nullable: true
        onSecond:
          type: boolean
          nullable: true
        onThird:
          type: boolean
          nullable: true
        inningHalf:
          type: string
          nullable: true
    gateway.market.v1.CricketState:
      type: object
      properties:
        innings:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.CricketInnings'
        currentInnings:
          type: integer
          format: int32
          nullable: true
        totalOvers:
          type: integer
          format: int32
          nullable: true
        phase:
          type: string
          nullable: true
        chase:
          $ref: '#/components/schemas/gateway.market.v1.CricketChase'
    gateway.market.v1.SoccerState:
      type: object
      properties:
        shootoutAttempts:
          type: array
          items:
            $ref: >-
              #/components/schemas/gateway.market.v1.SoccerPenaltyShootoutAttempt
    gateway.market.v1.MarketGroupStat:
      type: object
      properties:
        marketGroupId:
          type: string
          description: >-
            Market group identifier this stat applies to (matches
            EventMarketGroup.id)
        line:
          type: number
          format: decimal
          description: Line value for the group
          nullable: true
        current:
          type: number
          format: decimal
          description: Current line value for the group
          nullable: true
    gateway.market.v1.PeriodScore:
      type: object
      properties:
        number:
          type: integer
          format: int32
          description: '1-based within its type: the first overtime is 1, not 5'
        type:
          $ref: '#/components/schemas/gateway.market.v1.PeriodScoreType'
        label:
          type: string
          description: Period display label, sport-specific (e.g. Q1, OT)
        scores:
          type: array
          items:
            $ref: '#/components/schemas/gateway.market.v1.CompetitorScore'
          description: One entry per competitor, scoring this period alone, not cumulative
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
    gateway.hubs.v1.Hub:
      type: object
      properties:
        id:
          type: string
          description: Opaque hub ID for navigation
        title:
          type: string
          description: Hub display title
        image:
          type: string
          description: Hub banner image URL. Empty when absent
        subtitle:
          type: string
          description: Hub subtitle. Empty when absent
        icon:
          type: string
          description: Hub icon URL. Empty when absent
        status:
          $ref: '#/components/schemas/gateway.hubs.v1.HubStatus'
        startTime:
          type: string
          format: date-time
          description: Start of the hub's real-world event. Unset means no countdown
      description: Hub carries the display data for a link to a unified hub.
    gateway.market.v1.SportsTeamProvider:
      type: object
      properties:
        provider:
          $ref: '#/components/schemas/gateway.market.v1.Provider'
        providerId:
          type: string
          description: The provider id
    gateway.market.v1.ResolvedColor:
      type: object
      properties:
        light:
          type: string
          description: Hex color for light mode
        dark:
          type: string
          description: Hex color for dark mode
    gateway.market.v1.GameUpdate:
      type: object
      properties:
        id:
          type: integer
          format: int32
          description: Game update ID
        eventId:
          type: integer
          format: int32
          description: Event ID
        sportradarGameId:
          type: string
          description: Sportradar game ID
        type:
          type: string
          description: Game update type
        title:
          type: string
          description: Game update title
        subtitle:
          type: string
          description: Game update subtitle
          nullable: true
        subject:
          type: string
          description: Game update subject
          nullable: true
        team:
          type: string
          description: Team name
          nullable: true
        period:
          type: string
          description: Game period
          nullable: true
        clock:
          type: string
          description: Game clock
          nullable: true
        highlightAt:
          type: string
          format: date-time
          description: Highlight timestamp
          nullable: true
        createdAt:
          type: string
          format: date-time
          description: Creation timestamp
          nullable: true
    gateway.market.v1.MarketSideType:
      type: string
      enum:
        - MARKET_SIDE_TYPE_ERC1155
        - MARKET_SIDE_TYPE_INSTRUMENT
    gateway.market.v1.AssetPriceMarketType:
      type: string
      enum:
        - ASSET_PRICE_MARKET_TYPE_UNSPECIFIED
        - ASSET_PRICE_MARKET_TYPE_UP_DOWN
        - ASSET_PRICE_MARKET_TYPE_ABOVE_BELOW
        - ASSET_PRICE_MARKET_TYPE_RANGE
        - ASSET_PRICE_MARKET_TYPE_ONE_TOUCH
        - ASSET_PRICE_MARKET_TYPE_DATE
        - ASSET_PRICE_MARKET_TYPE_FIRST_TO_HIT
      description: >-
        How the market settles. ASSET_PRICE_MARKET_TYPE_UNSPECIFIED is returned
        for a market type newer than this schema: render the terms that are
        present.
    gateway.types.v1.AssetId:
      type: object
      properties:
        assetClass:
          $ref: '#/components/schemas/gateway.types.v1.AssetClass'
        symbol:
          type: string
          example: btc
          description: >-
            Lower-case symbol within the class, e.g. btc. Matches [a-z0-9-], at
            most 64 characters.
      description: >-
        Identifies one priced asset. The canonical string form is class:symbol,
        e.g. crypto:btc.
    gateway.types.v1.NullableAmount:
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
      nullable: true
    gateway.market.v1.AssetPriceRangeKind:
      type: string
      enum:
        - ASSET_PRICE_RANGE_KIND_UNSPECIFIED
        - ASSET_PRICE_RANGE_KIND_INTERIOR
        - ASSET_PRICE_RANGE_KIND_BELOW
        - ASSET_PRICE_RANGE_KIND_ABOVE
      description: >-
        Which side of a RANGE market is open. ASSET_PRICE_RANGE_KIND_UNSPECIFIED
        is returned on every market that is not a RANGE.
    gateway.market.v1.AssetPriceDirection:
      type: string
      enum:
        - ASSET_PRICE_DIRECTION_UNSPECIFIED
        - ASSET_PRICE_DIRECTION_UP
        - ASSET_PRICE_DIRECTION_DOWN
      description: >-
        ONE_TOUCH direction. ASSET_PRICE_DIRECTION_UNSPECIFIED is returned on
        every market that is not a ONE_TOUCH.
    gateway.market.v1.FootballDriveState:
      type: object
      properties:
        down:
          type: integer
          format: int32
          description: 1-4; 0 = not a scrimmage down (kickoffs, tries).
        yfd:
          type: integer
          format: int32
          description: Yards to go for a first down.
        possessionTeamId:
          type: string
          description: >-
            Internal team id of the side with the ball; empty when nobody has
            it.
        fieldPosition:
          $ref: '#/components/schemas/gateway.market.v1.FootballFieldPosition'
        startFieldPosition:
          $ref: '#/components/schemas/gateway.market.v1.FootballFieldPosition'
    gateway.market.v1.FootballTeamTimeouts:
      type: object
      properties:
        teamId:
          type: string
        used:
          type: integer
          format: int32
          description: >-
            optional: 0 (none left) must be distinguishable from not reported.
            The

            overtime allotment differs, so used is not derivable from remaining.
          nullable: true
        remaining:
          type: integer
          format: int32
          nullable: true
      description: Timeouts for the current half, not the game.
    gateway.market.v1.CricketInnings:
      type: object
      properties:
        number:
          type: integer
          format: int32
          nullable: true
        battingTeamId:
          type: string
          nullable: true
        runs:
          type: integer
          format: int32
          nullable: true
        wickets:
          type: integer
          format: int32
          nullable: true
        oversCompleted:
          type: integer
          format: int32
          nullable: true
        complete:
          type: boolean
          nullable: true
        ballsIntoOver:
          type: integer
          format: int32
          nullable: true
    gateway.market.v1.CricketChase:
      type: object
      properties:
        target:
          type: integer
          format: int32
          nullable: true
        runsNeeded:
          type: integer
          format: int32
          nullable: true
        ballsRemaining:
          type: integer
          format: int32
          nullable: true
        currentRunRate:
          type: number
          format: double
          nullable: true
        requiredRunRate:
          type: number
          format: double
          nullable: true
    gateway.market.v1.SoccerPenaltyShootoutAttempt:
      type: object
      properties:
        competitorId:
          type: string
        status:
          $ref: >-
            #/components/schemas/gateway.market.v1.SoccerPenaltyShootoutAttemptStatus
        playerId:
          type: string
        playerName:
          type: string
    gateway.market.v1.PeriodScoreType:
      type: string
      enum:
        - PERIOD_SCORE_TYPE_REGULATION
        - PERIOD_SCORE_TYPE_OVERTIME
      description: Quarters, halves and hockey periods are all REGULATION.
    gateway.market.v1.CompetitorScore:
      type: object
      properties:
        competitorId:
          type: string
          description: Internal team id
        score:
          type: integer
          format: int32
          description: Points scored in this period alone; always set, 0 is a real score
          nullable: true
    gateway.hubs.v1.HubStatus:
      type: string
      enum:
        - HUB_STATUS_ACTIVE
        - HUB_STATUS_ARCHIVED
      description: |-
        HubStatus matches the public unified Hub lifecycle.

         - HUB_STATUS_ACTIVE: The hub serves and appears in feed placements.
         - HUB_STATUS_ARCHIVED: The hub is retired and no longer serves.
    gateway.market.v1.Provider:
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
        - PROVIDER_ALTSPORTSDATA
        - PROVIDER_GRID
    gateway.types.v1.AssetClass:
      type: string
      enum:
        - ASSET_CLASS_CRYPTO
      description: AssetClass namespaces asset symbols.
    gateway.market.v1.FootballFieldPosition:
      type: object
      properties:
        teamId:
          type: string
          description: Side whose half the ball is in.
        yard:
          type: integer
          format: int32
          description: Within that half, 1-50; 50 = midfield.
    gateway.market.v1.SoccerPenaltyShootoutAttemptStatus:
      type: string
      enum:
        - SOCCER_PENALTY_SHOOTOUT_ATTEMPT_STATUS_NOT_TAKEN_YET
        - SOCCER_PENALTY_SHOOTOUT_ATTEMPT_STATUS_SCORED
        - SOCCER_PENALTY_SHOOTOUT_ATTEMPT_STATUS_MISSED

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.