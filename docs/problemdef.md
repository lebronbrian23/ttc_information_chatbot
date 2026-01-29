# Project Problem Definition - TTC Information Chatbot

## Problem Statement

TTC riders face a dual challenge of fragmented real-time information and absent predictive intelligence that prevents effective transit planning. With over 1.8 million daily riders, critical details about delays, service alerts, accessibility features, and real-time updates are scattered across multiple platforms including the TTC website, Twitter accounts (@TTChelps, @TTCnotices), and various technical data feeds. This fragmented landscape forces users to navigate multiple sources, parse technical data formats, and piece together incomplete information—often while already in transit and needing immediate answers.

More critically, riders lack the ability to plan ahead. While historical delay patterns and real-time data exist, there is no accessible way to answer planning-focused questions like "Will my route be delayed during my commute in 2 hours?" or "Which route is most reliable for my morning commute?" This results in commuters discovering problems only when they occur rather than planning around predicted disruptions. The absence of conversational, predictive transit intelligence means riders cannot make informed decisions about route selection, departure timing, or alternative transportation before problems impact their journey.

## Core Problem Components

***Information Fragmentation:**
- Service alerts published across website, multiple Twitter accounts, and real-time APIs
- No unified interface to query across all these sources simultaneously
- Users must know where to look for different types of information
- Real-time data exists but requires checking multiple apps and sources

**Accessibility Barriers:**
- Technical data formats (GTFS-RT feeds) not human-readable
- Critical information buried in lengthy web pages or tweet threads
- Mobile users struggle with complex navigation while commuting
- No conversational interface for simple questions like "Is Line 1 delayed?”

**Time Sensitivity:**
- Riders need instant answers about current disruptions affecting their route
- Delays in finding information can result in missed connections or extended wait times
- Real-time data exists but isn't easily accessible in natural language format
- Users waste valuable time cross-referencing multiple sources

**Gap in Predictive Intelligence:**
- No forward-looking insights: Existing apps show current status but don't predict delays 1-4 hours ahead when planning decisions are made
- Hidden historical patterns: Data exists showing which routes/times are reliably delayed, but isn't surfaced in user-friendly format
- No context-aware predictions: Weather, events, and other factors affecting transit aren't incorporated into delay forecasts
- Reactive information delivery: Users discover problems only after they occur, with no lead time to adjust plans
- Route reliability unknown: No way to compare historical reliability when choosing between alternative routes

## Target Users

**Primary Audience:**
- Daily TTC commuters seeking quick answers about their specific routes
- Occasional riders unfamiliar with navigating TTC information channels
- Accessibility-focused users needing station amenity information (elevators, restrooms, etc.)
- Tourists and visitors unfamiliar with Toronto's transit system

## User Scenarios:
“Is Line 1 delayed right now?"
"Will Line 1 be delayed during my 5pm commute?" [Planning-focused]
"Which route is more reliable - Line 1 or the 501 streetcar?" [Historical patterns]
"Which stations on my route have accessible restrooms?"
"Are there any planned service changes this weekend?"
"What's causing the delay at Bloor-Yonge?"
"Should I leave now or wait 30 minutes?" [Timing optimization]

### Input/Output Examples:

***Simple Example (MVP)***
Input: "Is there a delay on Line 1?" 
Output:
Line 1 (Yonge-University) Status:
Minor delays at Bloor-Yonge (signal problem)
Expected delay: 5-7 minutes
Last updated: 2 minutes ago

Alternative: Line 2 is running normally.

***Intermediate Example***
Input: "What's my commute from Dundas to North York Centre looking like?" 
Output:
Route: Dundas → North York Centre
Line 1 North: 32 minutes (normal: 25 min)
Delay at St. George: Track-level incident (+7 min)
Next train: 4 minutes
   
Alternative - Bus Route 97:
45 minutes via Yonge St
Less crowded, on-time performance: 85%

Recommendation: Take Line 1 but leave 10 minutes early.
Weather: Light snow may cause additional delays.


***Advanced Example***
Input: "I need to get to Scarborough Town Centre by 9 AM for a meeting. What's the best route?" Output:
Optimal Journey Plan (Arrival by 9:00 AM)
From: [Current Location] → Scarborough Town Centre

RECOMMENDED (87% on-time probability):
Depart: 7:42 AM | Arrive: 8:52 AM (8 min buffer)

Route: Line 2 East → Line 3 Scarborough RT
7:42 AM: Board at Dundas (Car 3 for faster exit)
8:15 AM: Transfer at Kennedy (Platform B, 2-min walk)
8:47 AM: Arrive STC

RISK FACTORS:
Kennedy transfer historically adds 3-5 min during rush
15% chance of RT delays (mechanical issues trend)
Weather: Clear, minimal impact expected

BACKUP PLAN (if delays occur):
GO Train + Bus: Depart 7:35 AM (arrives 8:45 AM)
Cost: $8.50 vs $3.35 TTC

LIVE MONITORING:
"I'll track your route and send alerts if delays occur. 
Reply 'status' for live updates during your commute."

BONUS: Starbucks at STC opens at 6 AM if you arrive early!


## Proposed Solution

A conversational AI chatbot that aggregates real-time TTC data from multiple sources, provides natural language responses to user queries about transit status, service alerts, station amenities, and schedule information, and enables proactive trip planning through predictive insights about future delays and historical reliability patterns.

**Key Features:**
- Multi-source data integration: Synthesizes TTC website, Twitter feeds, GTFS-RT data, and open data portal information into unified responses\n
- Natural language interface: Users ask questions conversationally rather than navigating menus or checking multiple apps
- Real-time status updates: Accesses live data feeds for current service status with source attribution
- Predictive insights: Forecasts delay likelihood 30 minutes to 4 hours ahead based on historical patterns and current conditions (our differentiator)
- Historical pattern analysis: Reveals route reliability trends to inform long-term commute decisions (our differentiator)
- Contextual, actionable responses: Provides relevant information with clear source citations, confidence levels, and planning recommendations
- Station amenities database with conversational access: Answer queries like "Which stations have accessible restrooms?" using a compiled database of amenities (restrooms, elevators, escalators, bike parking) with real-time elevator outage integration


## Technical Approach

**NLP Component**
- Text Processing:Parse and understand user questions about routes, delays, stations, and amenities
- Information Extraction: Extract relevant entities (line numbers, station names, times) from unstructured data sources (tweets, web pages, alerts)
- Response Synthesis:Generate coherent, conversational responses that summarize findings from multiple sources
- Intent Classification: Determine if query is about current status, predictions, historical patterns, or amenities

 LLM/Agent Role
- Query Router Agent: Determines which data sources to query based on user question type (service alerts → Twitter, real-time arrivals → GTFS-RT API, station info → website, predictions → ML model)
- Information Synthesizer: Aggregates data from multiple sources and presents unified, easy-to-understand responses
- Source Attribution: Provides references to original data sources for transparency
- Context Manager: Maintains conversation history for multi-turn dialogues

Data Sources
- TTC Website (structured pages and service alerts)
- Twitter: @TTChelps, @TTCnotices
- Toronto Open Data: TTC Bus Time Real-Time NVAS
- Toronto Open Data: TTC GTFS Real-Time feed
- Toronto Open Data: Historical delay datasets (subway, streetcar, bus delays)
- External: Weather data (for enhanced predictions in Phase 2)

**Predictive Modeling Component**

The predictive modeling component transforms the chatbot from a reactive information aggregator into a proactive planning assistant. By analyzing historical delay patterns, current conditions, and contextual factors, the system enables users to make informed decisions about route selection and departure timing before delays impact their journey.

Core Predictive Capabilities:
- Near-term forecasting (30 min - 4 hours ahead):** Helps users optimize departure times and choose alternative routes before leaving home
- Historical pattern insights: Reveals which routes/times are most reliable for long-term commute planning
- Context-aware predictions: Incorporates weather, events, and time-of-day patterns for improved accuracy

Phase 1 (Light Prediction):
- Simple delay predictor: Classify whether a route is "likely delayed" vs "likely on-time" for 30-60 minutes ahead (not current moment, which real-time data covers)
- Model: Logistic regression or decision tree
- Features: Route ID, time of day (hour), day of week, historical delay frequency
- Data: Past 3-6 months of TTC delay data from Toronto Open Data
- Baseline: Predict "always on-time" or "predict based on overall delay rate"
- Evaluation: Accuracy, Precision, Recall, F1 score on test set
- Integration: When a user asks "Is Line 1 delayed?" or "Should I take Line 1?", chatbot provides:
Current status: Real-time data from GTFS-RT and Twitter
Near-term prediction:** "Based on patterns, 70% likely on-time for next 30-60 minutes"
Planning value:** Helps users decide whether to leave now or wait

Example response:
"Line 1 Status:
✅ Currently: No delays reported (as of 3:45pm)
📊 Next hour: 70% likely on-time based on typical Thursday afternoon patterns
💡 Planning tip: Delays typically increase after 5pm rush hour"

Phase 2 (Predictive Modeling):
- Multi-horizon delay forecasting: Predict delay likelihood for  next 1-4 hours by route (the highest-value prediction)
- Arrival time prediction: Estimate actual vs scheduled arrival times
- Historical pattern insights: "Line 2 typically experiences 20% more delays on rainy Mondays" (very high value, easy to implement)
- Model: Gradient boosting (XGBoost/LightGBM) or LSTM for time series
- Enhanced features: Weather data, special events, holiday indicators, cascading delay effects, time-of-day patterns
- Data: 12+ months of historical TTC delay data, enriched with external factors
- Baseline comparison: Compare against simple models (logistic regression from Phase 1, historical average, always-predict-on-time)
- Evaluation: Classification metrics (accuracy, F1, ROC-AUC) + regression metrics (RMSE, MAE for arrival times)
- Integration:
Planning queries: "Line 1 at 5pm: 75% likely delayed (8-12 min). At 5:30pm: 60% likely delayed (5-8 min). Consider leaving at 5:45pm when delays typically decrease."
Route comparison: "Line 1 vs 501 streetcar: Line 1 has 68% on-time rate (avg 7 min delay). 501 has 55% on-time rate (avg 12 min delay). Line 1 recommended."
Cascade effects: "Current Line 1 delay at Yonge-Bloor likely to cause 5-10 min delays on connecting Line 2"
Weather-aware: "Heavy snow expected 4-7pm. Line 1 (subway) minimal impact. Surface routes 70% likely delayed."

Phase 3 (Production Scale Prediction - Future Vision):
- Real-time delay prediction: Continuously updated predictions every 2-5 minutes
- Cascade effect modeling: Predict how delays propagate through the network
- Commute time optimization: ML-powered routing that predicts fastest path given disruptions
- Demand forecasting: Predict crowding levels by route/time
- Anomaly detection: Automatically detect unusual patterns that might indicate issues
- Multi-horizon forecasting: Predictions for 15min, 1hr, 4hr, next day
- Model: Deep learning (LSTM, Transformer) with online learning for continuous improvement
- Integration: 
Proactive notifications: "Your usual 5pm Line 1 route: 80% delay probability in 30 min. Leave now or take 501 streetcar instead."
Smart routing: "Normally take Line 1, but predicted 15min delay. Line 2 + bus 8 min faster today."
Crowding alerts: "Line 1 predicted 90% capacity at your stop at 5pm. Wait until 5:15pm for less crowded train."
Please note Future Vision is included to further help us understand the differences between the phases as well as future inspiration. It is out of scope for this project 

## Project Scope

***Phase 1: Core Chatbot MVP with Light Prediction (Weeks 1-6)***

Core Functionality:
- Chatbot interface accepting natural language queries
- Integration with 3-4 primary data sources (GTFS-RT, TTC website, Toronto Open Data)
- Basic query types: current service alerts, real-time arrivals, general delay status, route-specific issues
- Web-based chat interface with responsive design
- Source attribution for all factual claims
- Deployed web application accessible to online users
- Automated data pipeline with real-time refresh
- Basic CI/CD with Docker

LLM/NLP Component:
- Baseline LLM: GPT-4/GPT-3.5 with engineered prompts
- Intent classification and entity extraction
- Natural language response generation

Predictive Modeling Component:
- Simple delay classifier (logistic regression or decision tree)
- Features: Route, time of day, day of week, historical frequency
- Data: 3-6 months historical delay data
- Baseline comparison and evaluation (Accuracy, Precision, Recall, F1)
- Integration: Show current status + delay probability prediction

Success Criteria:
- ✅ Deployed: Web chatbot accessible via public URL
- ✅ LLM/NLP: Query processing with >85% accuracy on 50-question test set
- ✅ Predictive Model: Delay classifier predicting 30-60 min ahead with >70% accuracy, evaluated against baseline, demonstrates planning value
- ✅ Response time <5 seconds average
- ✅ 100% source attribution
- ✅ Clean, reproducible codebase with documentation

---

***Phase 2: Enhanced Intelligence with Advanced Prediction (Weeks 7-12)***

Enhanced Functionality:
-Voice to text generation 
- Station amenity database (elevators, restrooms, accessibility, WiFi, bike parking)
- Historical delay pattern analysis and visualization
- Planned service changes and weekend schedules
- Advanced query types: amenity searches, historical patterns, comparative analysis, multi-hop questions
- Multi-turn conversation context
- Rich media responses (maps, delay charts)
- Enhanced deployment with monitoring dashboards
- Comprehensive CI/CD with automated testing

LLM/NLP Component (Advanced):
- Fine-tuned open-source LLM (Llama 3.1 8B or Mistral 7B) on TTC-specific data
- RAG (Retrieval-Augmented Generation) with vector database
- Multi-model evaluation (GPT-3.5 vs GPT-4 vs fine-tuned vs RAG)
- Custom NER for TTC entities
- Evaluation: Accuracy, F1, retrieval quality (MRR, NDCG), hallucination rate (<5%)

Predictive Modeling Component (Advanced):
- Delay probability forecasting:** Predict likelihood for next 1-4 hours by route
- Arrival time prediction:** Estimate actual vs scheduled times
- Pattern-based forecasting: Historical trend insights
- Model: XGBoost/LightGBM or LSTM for time series
- Enhanced features: Weather, special events, holidays, cascading delays
- Data: 12+ months historical data enriched with external factors
- Evaluation: Classification (accuracy, F1, ROC-AUC) + regression metrics (RMSE, MAE)
- Integration: Multi-horizon predictions, cascade effects, proactive route suggestions

Deployment & Operations:
- Reliable cloud hosting (stable, publicly accessible)
- Monitoring dashboards (Prometheus + Grafana)
- Automated testing suite (unit, integration, E2E)
- Enhanced CI/CD with rollback capability
- Performance optimization (<3 second response time)
- Error logging and tracking

Success Criteria:
- ✅ Deployed: Stable application with monitoring, >95% uptime during testing
- ✅ LLM/NLP: Fine-tuned model >10% improvement over baseline, comprehensive evaluation
- ✅ Predictive Model: Advanced forecasting >75% accuracy, 15%+ improvement over Phase 1
- ✅ Advanced query support >85% accuracy
- ✅ Response time <3 seconds
- ✅ >80% test coverage
- ✅ Professional documentation (API docs, setup guide, architecture diagrams)

---

***Phase 3: Intelligent Platform with Production-Grade Infrastructure (Future Vision)***
Please note Future Vision is included to further help us understand the differences between the phases as well as future inspiration. It is out of scope for this project. You are welcome to skip to the Final Section 

Advanced Features:
- Native mobile apps (iOS/Android) and PWA
- Multi-modal support (voice interface)
- Proactive notifications (route subscriptions with predicted delay alerts)
- Personalized routing suggestions based on disruptions
- "Smart commute" feature (learns patterns, predicts needs)
- Trip planning integration (Google/Apple Maps)
- User accounts with preferences
- Public API for third-party integrations
- Multilingual support

LLM/NLP Component (Production-Scale):
- Ensemble of specialized models
- Reinforcement learning from user feedback (RLHF)
- Personalization engine
- Multi-language support
- Voice interface with advanced NLU
- Proactive conversational suggestions

Predictive Modeling Component (Production-Scale):
- Real-time predictions: Updated every 2-5 minutes
- Cascade effect modeling: How delays propagate through network
- Commute optimization: ML-powered routing for fastest path
- Demand forecasting: Crowding level predictions
- Anomaly detection: Unusual pattern identification
- Multi-horizon forecasting: 15min, 1hr, 4hr, next day
- Model: Deep learning (LSTM, Transformer) with online learning
- Integration: Push notifications, smart routing, crowding alerts

Deployment & Operations (Production-Grade):
- Enterprise infrastructure (Kubernetes auto-scaling)
- High availability (99.9% SLA, multi-region, load balancing)
- Advanced monitoring (real-time alerts, incident response)
- Security & compliance (encryption, privacy policies)
- Performance at scale (<2 sec with thousands of users)
- CDN and global caching
- Disaster recovery (backups, failover)

Success Criteria:
- ✅ Multi-platform deployment (web, iOS, Android)
- ✅ Production NLU with >90% query resolution
- ✅ Real-time forecasting >80% accuracy with demonstrated commute savings
- ✅ >10,000 monthly active users
- ✅ 99.9% uptime SLA
- ✅ API used by 3+ third-party apps
- ✅ User satisfaction >4.5/5

## Unique Value Proposition

Unlike existing TTC information channels that only show current status and require users to know where to look and how to interpret technical data, this chatbot serves as an intelligent planning assistant that:
- Understands natural language questions across various formats and intents, from simple status checks to complex planning queries
- Aggregates fragmented real-time information from multiple official sources (TTC website, Twitter, GTFS-RT feeds) including an amenities database (especially restrooms) that TTC doesn't officially publish, into unified, conversational responses
- Enables proactive planning through predictions:
  - Multi-horizon delay forecasting (30 min to 4 hours ahead) for departure time optimization
  - Historical pattern insights revealing which routes/times are most reliable
  - Context-aware predictions incorporating weather and current conditions
- Presents actionable insights in conversational format optimized for mobile users, with clear source attribution and confidence levels
- Learns and improves through fine-tuning on TTC-specific terminology and user feedback

The key differentiator: The system transforms reactive problem-discovery into proactive route planning. Instead of telling users about delays after they occur, it helps them plan around predicted disruptions before leaving home—answering critical planning questions like "Should I leave now or in 30 minutes?" and "Which route is most reliable for my daily commute?" that no existing transit app addresses conversationally.

The chatbot gives commuters the information they need, when they need it (before problems occur), in the format that's easiest to consume (natural conversation)—all while being accessible to online users through a deployed web application.
