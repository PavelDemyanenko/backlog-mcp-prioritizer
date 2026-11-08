# Backlog MCP Prioritizer server image. Build the jar first: mvn -DskipTests package
#   docker build -t backlog-mcp-prioritizer .
# Started by the MCP host over stdio (-i); no ports are exposed:
#   docker run -i --rm -e YOUTRACK_BASE_URL -e YOUTRACK_TOKEN backlog-mcp-prioritizer

FROM eclipse-temurin:25-jre-noble AS extract
WORKDIR /extract
COPY target/backlog-mcp-server.jar app.jar
# Layers: dependencies change rarely and stay cached; a code change rebuilds only the application layer
RUN java -Djarmode=tools -jar app.jar extract --layers --destination layers

FROM eclipse-temurin:25-jre-noble
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=extract --chown=app:app /extract/layers/dependencies/ ./
COPY --from=extract --chown=app:app /extract/layers/spring-boot-loader/ ./
COPY --from=extract --chown=app:app /extract/layers/snapshot-dependencies/ ./
COPY --from=extract --chown=app:app /extract/layers/application/ ./
# AOT cache: the MCP host starts the server for every session, so cold start matters.
# The training run refreshes the context and exits; GC/object-header flags must match ENTRYPOINT.
RUN java -XX:+UseSerialGC -XX:+UseCompactObjectHeaders -XX:AOTCacheOutput=app.aot \
        -Dspring.context.exit=onRefresh -jar app.jar < /dev/null
USER app
# ADRs of the user's project can be mounted here: -v "$PWD/docs/adr:/adr:ro" (default ADR_DIR in the image)
ENV ADR_DIR=/adr
# exec: java is PID 1, receives the MCP host's stdin and SIGTERM. JAVA_OPTS: extra runtime flags.
ENTRYPOINT ["sh", "-c", "exec java -XX:+UseSerialGC -XX:+UseCompactObjectHeaders -XX:AOTCache=app.aot $JAVA_OPTS -jar app.jar"]
