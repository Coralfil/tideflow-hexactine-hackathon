# TideFlow Hexactine: Business Case and Overview

## 1. Executive Summary

TideFlow Hexactine is an AI-powered personal operating environment tailored to mitigate context switching, cognitive overload, and time management friction for creative professionals and individuals navigating ADD. By fusing a persistent bitemporal graph memory system (Hexactine) with an autonomous scheduling engine (Tidal) and a proactive agent gatekeeper (Nemoclaw), the platform ensures no idea is lost, no side quest derails core objectives, and momentum remains constant. 

## 2. Problem Statement

Creative professionals and developers frequently battle "context collapse." The modern workflow is a barrage of disjointed applications, unstructured notes, and abrupt task switching. For individuals with ADD, this environment turns side quests into permanent distractions. Existing time management tools track discrete tasks but fail to preserve the relational context connecting an abstract idea to its implementation. When a user shifts focus, the contextual momentum is entirely lost.

## 3. Solution Overview

TideFlow Hexactine solves context collapse by introducing an active workspace hub that understands relationships.

* **Hexactine Graph Memory:** Built on a dual-mode Neo4j/Relate backend, Hexactine maps the user's thoughts, projects, and tasks as nodes in a persistent graph. It tracks bitemporal breadcrumbs, meaning it knows both when an idea was created and when it was last active in the user's mind.
* **Tidal Scheduler:** An intelligent orchestration engine that calculates momentum scores. It surfaces high-priority work during deep focus periods and catalogs tangential ideas (side quests) for later retrieval, preventing immediate distraction while validating the user's creativity.
* **Nemoclaw Gatekeeper:** A retriever agent that executes tasks autonomously when permissions allow. It retrieves context for stalled projects and actively pulls relevant graph nodes back into the workspace when the user is ready to resume a derailed thread.

## 4. Kane CLI and Rook Integration

A core requirement for personal AI environments is absolute reliability. To guarantee execution stability, TideFlow Hexactine is continuously validated using TestMu AI's Kane CLI and Rook lifecycle hooks.

* **Agentic Verification:** Kane CLI agent processes execute headless browser assertions against the TideFlow UI, verifying that bitemporal breadcrumbs and modal unmounting happen precisely as designed. The CLI acts as our automated quality assurance gate before any code reaches production.
* **Rook Lifecycle Hooks:** We embedded Rook within our testing and deployment pipelines. The `.testmuai/rook/` hooks run automated network idle validations and UI state checks, ensuring our bitemporal graph updates reflect accurately in the frontend without race conditions.
* **Impact:** This integration eliminated four persistent E2E snapshot truncation errors during development, providing an airtight guarantee that the user's graph data remains pristine.

## 5. Alignment with Judging Criteria

### Innovation
TideFlow Hexactine moves beyond linear task lists. It applies bitemporal graph science to personal time management, allowing an AI to understand the semantic distance between a user's current focus and a past idea. 

### Technical Execution
The platform is built on a robust, asynchronous FastAPI backend integrated directly with Neo4j and Relate. The frontend is a highly reactive React 19 / Vite 8 application. All operations are packaged into a zero-configuration executable for immediate deployment. 

### Usability
We designed the interface with interactive controls and fluid animations specifically themed around graph science. It is intuitive, deeply immersive, and operates instantly without demanding manual categorization from the user. 

## 6. Deployment and Usage

The enclosed executable (`TideFlow_Hexactine.exe` or `launcher.exe`) requires zero configuration. It mounts the pre-built React frontend and serves the entire application stack from a single local port, initializing the internal Relate database on startup. 

**Hackathon Submission URL:**
[Submit Here via TestMu AI Event Portal](https://www.surveymonkey.com/r/kane-cli-hackathon-submission) (Referenced from the Kane CLI Luma event page).
