Local exact-version negative tests for configuration-adjusted health-only deployment.
Run with JDK21: mvn compile dependency:build-classpath -Dmdep.outputFile=cp
java -cp "target/classes:$(cat cp)" MatcherProbe ../alpha-init/config/certify-default.properties
The probe reconstructs the original **/actuator/** baseline in memory before comparing the exact /actuator/health replacement. No server is launched. Only GET health changes from denied to intended anonymous access. Other endpoint patterns remain unchanged. This is NOT unmodified-release conformance.
