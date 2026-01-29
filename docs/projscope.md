Project Scope: 12-13 Weeks vs 14-15 Weeks

## 12-13 Week Scope (Team Preference: Quality Over Speed)

### **Phase 1: Core MVP (Weeks 1-6)**

#### **In Scope:**

**Data Pipeline:**
- ✅ Integration with 3-4 data sources:
  - GTFS-RT real-time feed
  - Twitter (@TTChelps, @TTCnotices)
  - TTC website (service alerts)
  - Toronto Open Data (historical delays)
- ✅ Automated data refresh (every 2-5 minutes)
- ✅ PostgreSQL database for structured storage
- ✅ Basic data validation and error handling
- ✅ 3-6 months historical delay data collected

**LLM/NLP:**
- ✅ GPT-4 or GPT-3.5-turbo via API
- ✅ Prompt engineering for query understanding
- ✅ Intent classification (alert vs arrival vs prediction)
- ✅ Entity extraction (routes, stations, times)
- ✅ Response generation with source attribution

**Predictive Modeling:**
- ✅ Simple delay classifier (logistic regression or decision tree)
- ✅ Predicts 30-60 minutes ahead (not "right now")
- ✅ Features: Route ID, hour, day of week, historical frequency
- ✅ Train/test split with evaluation
- ✅ Baseline comparison (always-on-time, historical average)
- ✅ Metrics: Accuracy, Precision, Recall, F1
- ✅ Integration into chatbot responses

**Backend:**
- ✅ FastAPI REST API
- ✅ Query routing logic (determines which data source to query)
- ✅ Response synthesis from multiple sources
- ✅ Basic caching (Redis for frequently asked queries)
- ✅ Error handling and logging

**Frontend:**
- ✅ React-based chat interface
- ✅ Conversation display (user messages + bot responses)
- ✅ Session-based conversation history
- ✅ Suggested example questions
- ✅ Mobile-responsive design
- ✅ Source citation display
- ❌ No visual polish required (functional UI is fine)

**Deployment:**
- ✅ Dockerized application
- ✅ Cloud deployment (AWS/GCP/Azure)
- ✅ Public URL accessible
- ✅ Basic CI/CD (automated deployment on merge to main)
- ✅ Environment-based configuration

**Documentation:**
- ✅ README with setup instructions
- ✅ Basic API documentation
- ✅ Code comments for key functions
- ✅ Model evaluation report (simple)

**Testing:**
- ✅ 30-40 question test dataset
- ✅ Manual testing of core features
- ✅ Basic unit tests for critical functions (~40-50% coverage)

---

### **Phase 2: Enhanced Intelligence (Weeks 7-13)**

#### **In Scope:**

**Enhanced Data:**
- ✅ 12+ months historical delay data
- ✅ Amenity database compilation:
  - **Restroom locations** (primary focus - manual compilation)
  - **Real-time elevator/escalator status** (from TTC feed)
  - **Basic accessibility features** (from TTC data)
- ✅ Weather data integration (OpenWeather API or similar)
- ✅ Data quality monitoring

**Advanced Predictive Modeling:**
- ✅ **Multi-horizon forecasting model:**
  - XGBoost or LightGBM
  - Predicts delay likelihood 1-4 hours ahead
  - Features: weather, time-of-day, special events, historical patterns
  - Evaluation: accuracy, F1, ROC-AUC
- ✅ **Historical pattern analysis:**
  - Route reliability insights ("Line 2: 35% delayed Monday mornings")
  - Comparative route analysis
  - Descriptive statistics by route/time/day
- ✅ Baseline comparisons showing >15% improvement over Phase 1 model
- ✅ Comprehensive evaluation report

**LLM/NLP Enhancement - Choose ONE:**

**Option A: RAG (Retrieval-Augmented Generation)** ⭐ Recommended
- ✅ Vector database setup (Pinecone or Weaviate)
- ✅ TTC documentation embedding
- ✅ Retrieval pipeline for contextual information
- ✅ Integration with response generation
- ✅ Evaluation: retrieval quality (MRR, NDCG)

**Option B: Fine-tuned Model**
- ✅ Collect/create TTC-specific Q&A dataset
- ✅ Fine-tune Llama 3.1 8B or Mistral 7B
- ✅ Training infrastructure setup
- ✅ Model evaluation vs baseline
- ✅ Deployment optimization

**Rationale for choosing ONE:** Both are substantial work. RAG is faster to implement, more flexible, and easier to debug. Fine-tuning is more impressive but higher risk in limited time.

**Advanced Features:**
- ✅ Multi-turn conversation context
- ✅ Advanced query types:
  - Amenity searches ("Which stations have restrooms?")
  - Historical patterns ("Is Line 2 usually delayed on Mondays?")
  - Comparative analysis ("Which route is more reliable?")
  - Weather-aware predictions
- ✅ Map integration (showing affected routes/stations)
- ✅ Basic visualizations (delay pattern charts using Chart.js or Recharts)

**Backend Enhancements:**
- ✅ Advanced agent orchestration (query routing to prediction model, RAG, real-time data)
- ✅ Conversation state management
- ✅ Performance optimization (response time <3 seconds)
- ✅ Enhanced caching strategy
- ✅ Analytics tracking (usage patterns, popular queries)

**Frontend Improvements:**
- ✅ Map display for stations/routes
- ✅ Basic charts for delay patterns
- ✅ Improved conversation UI (loading states, error messages)
- ✅ Better mobile experience
- ❌ Still no heavy visual polish (functional improvements only)

**Deployment & Operations:**
- ✅ Monitoring dashboards:
  - Basic logging (application logs, error tracking)
  - Uptime monitoring
  - Performance metrics (response time, query volume)
  - **Skip Grafana** (use simpler tools like cloud provider dashboards)
- ✅ Enhanced CI/CD:
  - Automated test suite runs before deployment
  - Rollback capability
- ✅ Production stability improvements
- ✅ Error alerting (email/Slack notifications)

**Documentation:**
- ✅ Comprehensive API documentation
- ✅ Architecture diagrams
- ✅ Setup guide (detailed)
- ✅ Model evaluation report:
  - Methodology
  - Results with visualizations
  - Baseline comparisons
  - Metrics explanation
- ✅ User guide (how to use the chatbot)

**Testing:**
- ✅ Expanded test dataset (100+ questions)
- ✅ 60-70% test coverage
- ✅ Integration tests
- ✅ End-to-end tests for critical user flows
- ❌ Skip comprehensive E2E testing (focus on critical paths)

---

### **Out of Scope for 12-13 Weeks:**

**Descoped to manage timeline:**
- ❌ **Both RAG AND fine-tuning** (choose one)
- ❌ **Custom NER model** (use standard entity extraction from GPT)
- ❌ **Comprehensive amenity database** (WiFi, bike parking - focus on restrooms + elevators only)
- ❌ **Cascade effect modeling** (how delays propagate between routes)
- ❌ **Arrival time prediction** (competing with GTFS-RT is complex)
- ❌ **Advanced monitoring** (Prometheus + Grafana dashboards)
- ❌ **80%+ test coverage** (60-70% is acceptable)
- ❌ **UI polish and design** (functional > beautiful)
- ❌ **Voice interface or mobile apps**
- ❌ **User accounts and personalization**

---

## 14-15 Week Scope (Extended Timeline)

### **Everything from 12-13 Weeks PLUS:**

**Week 13-14: Additional ML/NLP Features**

**If you chose RAG in Phase 2, add:**
- ✅ **Fine-tuned model** in addition to RAG
- ✅ A/B comparison: GPT-3.5 vs GPT-4 vs RAG vs Fine-tuned
- ✅ Ensemble approach (use different models for different query types)

**If you chose Fine-tuning in Phase 2, add:**
- ✅ **RAG system** in addition to fine-tuning
- ✅ Comprehensive model comparison

**Additional Predictive Features:**
- ✅ **Cascade effect modeling:**
  - Predict how Line 1 delays affect Line 2
  - Transfer station impact analysis
- ✅ **Arrival time prediction:**
  - Compete with GTFS-RT predictions
  - "Scheduled 3 min, likely 5-7 min based on patterns"
- ✅ **Custom NER model:**
  - Fine-tuned entity extraction for TTC-specific terms
  - Better handling of route names, landmarks, colloquial terms

**Week 14-15: Production Quality Enhancements**

**Comprehensive Amenity Database:**
- ✅ **Full amenity coverage:**
  - WiFi availability (TTC Connect locations)
  - Bike parking locations and capacity
  - Presto machine locations
  - Customer service hours by station
  - Accessible parking spots
- ✅ Verification status (verified vs reported)
- ✅ User contribution mechanism (optional)

**Advanced Monitoring & Operations:**
- ✅ **Prometheus + Grafana dashboards:**
  - Real-time metrics visualization
  - Historical performance trends
  - Custom alerts and thresholds
- ✅ Detailed error tracking (Sentry integration)
- ✅ Performance profiling and optimization
- ✅ Load testing and capacity planning

**Enhanced Testing:**
- ✅ **80%+ test coverage:**
  - Comprehensive unit tests
  - Integration tests for all components
  - End-to-end tests for all user journeys
- ✅ Performance testing
- ✅ Security testing (basic penetration testing)

**UI Polish (Your Priority):**
- ✅ **Professional design system:**
  - Consistent color palette and typography
  - Polished component library
  - Smooth animations and transitions
  - Delightful micro-interactions
- ✅ **Advanced visualizations:**
  - Interactive delay pattern charts (D3.js or Plotly)
  - Heat maps showing delay hotspots
  - Animated route maps
- ✅ **Accessibility improvements:**
  - WCAG 2.1 AA compliance
  - Keyboard navigation
  - Screen reader optimization
  - Color contrast validation
- ✅ **Dark mode**
- ✅ **Responsive design perfection** (desktop, tablet, mobile)

**Documentation Polish:**
- ✅ Video demo (recorded walkthrough)
- ✅ Interactive API documentation (Swagger UI with examples)
- ✅ Blog post or case study write-up
- ✅ Presentation materials for demo day
- ✅ Code quality review and refactoring

---

## Comparison Table: 12-13 Weeks vs 14-15 Weeks

| Component | 12-13 Weeks | 14-15 Weeks |
|-----------|-------------|-------------|
| **Data Sources** | 3-4 sources | Same |
| **Predictive Models** | Simple classifier + Multi-horizon XGBoost | Same + Cascade modeling + Arrival prediction |
| **LLM/NLP** | RAG **OR** Fine-tuning | RAG **AND** Fine-tuning + Custom NER |
| **Amenity Database** | Restrooms + Elevators | Full coverage (WiFi, bike parking, etc.) |
| **UI Quality** | Functional, not polished | Professional design + polish |
| **Visualizations** | Basic charts | Advanced interactive visualizations |
| **Monitoring** | Basic logging + uptime | Prometheus + Grafana dashboards |
| **Test Coverage** | 60-70% | 80%+ |
| **Testing Depth** | Unit + key integration tests | Comprehensive unit/integration/E2E |
| **Documentation** | Good (API docs, reports) | Excellent (video, case study, presentations) |
| **Accessibility** | Basic responsive design | WCAG 2.1 AA compliant |
| **Demo Quality** | Working demo | Polished, professional demo |

---

## Recommended Approach

### **For Team That Wants Quality Over Speed:**

**Choose 13-14 Week Timeline:**

**Weeks 1-6: Phase 1** (as defined above)
- Solid MVP with all core features
- No rushing, proper testing
- Clean code from the start

**Weeks 7-12: Phase 2 Core** 
- Advanced predictions
- Choose RAG (faster) or Fine-tuning (more impressive)
- Amenity database (restrooms + elevators)
- Basic monitoring
- 60-70% test coverage
- Functional UI improvements

**Weeks 13-14: Polish & Extensions**
- **If you care about polish:** UI design improvements, visualizations
- **If team cares about ML:** Add second LLM approach (RAG + Fine-tuning)
- **If team cares about features:** Full amenity database, cascade modeling
- **For everyone:** Comprehensive documentation, demo preparation

---

## Decision Framework

### **Go with 12-13 Weeks if:**
- ✅ Hard deadline (academic calendar)
- ✅ Team okay with functional UI (no polish)
- ✅ Choosing ONE LLM enhancement (RAG or Fine-tuning)
- ✅ Limited amenity database (restrooms + elevators only)
- ✅ Basic monitoring is acceptable

**Deliverable:** Strong, functional project demonstrating all core capabilities

---

### **Go with 14-15 Weeks if:**
- ✅ Flexible deadline
- ✅ You want polished UI and visualizations
- ✅ Team wants to explore both RAG and Fine-tuning
- ✅ Comprehensive amenity database desired
- ✅ Production-quality monitoring and testing

**Deliverable:** Portfolio-centerpiece project with professional polish

---

## My Recommendation for Your Team

Based on "team wants to take their time and not be rushed":

### **Target: 13-14 Weeks**

**Week 1-6: Phase 1** (relaxed pace, quality focus)
- Core MVP with proper testing
- Clean, well-documented code
- Team learns tools without pressure

**Week 7-12: Phase 2 Core** (steady progress)
- Advanced features without rushing
- Choose RAG (recommended - easier to implement well)
- Good test coverage and documentation

**Week 13-14: Choice Period**
- **Week 13:** Add second LLM approach OR UI polish OR comprehensive testing
- **Week 14:** Documentation polish, demo prep, final testing

**This gives you:**
- ✅ No rushing or panic
- ✅ High-quality deliverable
- ✅ Time to learn and iterate
- ✅ Flexibility in final 2 weeks
- ✅ Professional demo-ready project

---

## Scope Summary

### **12-13 Week Scope (Functional, Complete)**
```
✅ Deployed chatbot with 3-4 data sources
✅ Simple + Advanced predictive models (>15% improvement)
✅ RAG OR Fine-tuning (choose one)
✅ Restrooms + Elevator amenity database
✅ Multi-turn conversations, historical patterns
✅ Maps + basic visualizations
✅ 60-70% test coverage
✅ Good documentation
✅ Functional UI (not polished)
✅ Basic monitoring
```

### **14-15 Week Scope (Polished, Comprehensive)**
```
Everything above PLUS:
✅ RAG AND Fine-tuning (both)
✅ Cascade modeling + Arrival prediction
✅ Full amenity database (WiFi, bike parking, etc.)
✅ UI polish + professional design
✅ Advanced visualizations
✅ 80%+ test coverage
✅ Prometheus + Grafana monitoring
✅ Comprehensive E2E testing
✅ Video demo + case study
✅ WCAG accessibility compliance
```
