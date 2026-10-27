# Running the conformance bridge inside each module's own api-testrig

The problem statement's default mode is per-module: Inji Certify's conformance
results run inside Inji Certify's api-testrig, and Inji Verify's inside Inji
Verify's. This folder documents how to drop the bridge into either rig so the
results land in that rig's normal TestNG/EmailableReport report (and its S3/MinIO
upload, when the rig is configured for it).

The bridge test class is plain TestNG plus `org.json` (both rigs already depend on
`com.github.openjson:openjson`) and needs none of the rig's MOSIP-environment setup
(Keycloak, PMS, DB). It only reads the JSON produced by `scripts/conformance_runner.py`.

## Inji Certify (issuer plan)

1. Clone the rig: `git clone https://github.com/mosip/inji-certify` (the
   `api-test/` folder is the rig; the problem statement's link
   `github.com/inji/inji-certify` redirects to the MOSIP org).
2. Copy the test class into the rig:

   ```powershell
   copy apitestrig-bridge\src\main\java\inji\conformance\ConformanceResultsTest.java `
        inji-certify\api-test\src\main\java\inji\conformance\ConformanceResultsTest.java
   ```

3. Copy the suite file into the rig's `testNgXmlFiles` folder. The rig's
   `InjiTestRunner` runs every file there whose name contains "mastertestsuite":

   ```powershell
   copy apitestrig-bridge\src\main\resources\testNgXmlFiles\conformanceCertifyMasterTestSuite.xml `
        inji-certify\api-test\testNgXmlFiles\
   ```

4. Run the conformance harness first, so there is a results file:

   ```powershell
   python scripts\conformance_runner.py --component certify --output conformance-results.json
   ```

5. Build and run the rig the way its own README describes (`mvn clean install
   -Dgpg.skip=true -Dmaven.gitcommitid.skip=true`, then run the generated JAR),
   adding the two bridge properties to the run (the rig's own `env.*` properties
   are still needed for its normal startup):

   ```powershell
   java -Dconformance.results=<absolute path>\conformance-results.json `
        -Dconformance.component=certify `
        -jar inji-certify\api-test\target\apitest-injicertify-*.jar
   ```

   `InjiTestRunner` picks up `conformanceCertifyMasterTestSuite.xml` because its
   file name contains "mastertestsuite", and the conformance outcomes appear in
   the rig's normal report output.

## Inji Verify (verifier plan)

Same steps against `https://github.com/mosip/inji-verify`, using
`conformanceVerifyMasterTestSuite.xml` and `-Dconformance.component=verify`.

## Notes and honest caveats

* The suite XMLs register MOSIP's `EmailableReport` listener. When run inside the
  real rig, the rig's own `InjiTestRunner` setup provides the environment labels
  and configuration the listener needs; the S3/MinIO upload happens only when the
  rig is configured with `push-reports-to-s3=yes` and valid MinIO credentials, as
  with any api-testrig run.
* We verified the bridge end to end with `EmailableReport` outside the full rig
  (see the main README, verification status). Execution inside `InjiTestRunner`
  with a full MOSIP environment is documented here but was not run by us.
* `benchmark.allowWarnings` and `--min-pass-rate` behave the same inside the rig;
  the standalone runner's build-gating exit code is provided by
  `ConformanceBridgeRunner`, so inside the rig use the standard TestNG result
  (failed tests fail the rig's build) as the gate.
