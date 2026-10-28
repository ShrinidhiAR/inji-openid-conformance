# Isolated native component api-test integration

STATUS 2026-10-28: the native rig, local MinIO upload and the combined/one-command entry now have hosted-runner runs (Certify-only default-all path proven; combined Certify + Verify via the phased workflow: Certify FAILED, Verify REVIEW). See the top-level README. Verify-only via the one-command script and full official plans are untested. The older notes below describe the design and are kept as written.

Do not run normal InjiTestRunner.main to test this integration. Its normal startup
can create users, change accounts and clean a database, and its process exitcode
is not a reliable test gate. Earlier instructions that copied the bridge into an
ordinary suite directory then launched the rig JAR were unsafe and are replaced
by this conformance-only mode.

## What is implemented

- stage_isolated.py checks exact upstream commit and clean tracked api-test files,
  then copies only api-test to a NEW temporary directory. Originals stay untouched.
- Exactly one master suite, one project testclass and the native EmailableReport
  listener are allowed. Extra suites/classes/listeners fail before discovery.
- Project IsolatedRigLauncher compiles inside each real componentclasspath and
  calls native startTestRunner, never main, suiteSetup or BaseTestCase.initialize.
- @BeforeSuite invokes the pinned official Pythonlibrary through the projectrunner
  with fresh runid, same component endpoint, explicit configuration and CA.
- Native TestNG XML independently gates failure, skip, empty and configuration
  failure. WARNING and REVIEW never satisfy this isolated benchmark.
- Slack disabled. Optional private localS3properties permit only loopbackendpoint
  and automationtests bucket, nativeupload plus independent bytehashreadback.
  This S3 branch is compiled, NOT runtimeMinIOvalidated. Keep private nativelogs:
  upstream S3Adapter can log accesskeys. Surround JVM with an external timeout.

## Stage and compile

Requires Python3 with scripts/requirements.txt, JDK21, Maven, clean exactpinned
upstream source (pins in stage_isolated.py). The destination must not exist.

```sh
python3 rig-integration/stage_isolated.py --component certify \
  --upstream /path/to/pinned-certify --destination /tmp/certify-conformance-rig
mvn -f /tmp/certify-conformance-rig/pom.xml -DskipTests \
  -Dgpg.skip=true -Dmaven.gitcommitid.skip=true compile dependency:build-classpath \
  -Dmdep.outputFile=/tmp/certify-conformance-classpath
```

Repeat with component verify and its pinned source. No runtime is started above.

## Local fixture acceptance, not product evidence

```sh
python3 rig-integration/tests/native_fixture_prototype.py --component certify \
  --rig-classpath "/tmp/certify-conformance-rig/target/classes:$(cat /tmp/certify-conformance-classpath)"
```

This creates a temporary fake HTTPsuite and calls actual native discovery,
BeforeSuite officiallibrary and reportgeneration. It checks1FAILEDfixturemodule
becomes realTestNG1failedrow and launcherexit1. The fake endpoint is explicitly
fixtureOnly loopback; default launcher mode accepts only https://suite:8443.
Repeat for Verify with its actualcompiledclasspath. Native guardtests use
NATIVE_RIG_TEST_CP and optional JAVA environment variables.

Real invocation needs an audited private invocationmanifest/config, disposable
HTTPS endpoints and a wired handoffadapter. The generic runner currently rejects
WAITING without an adapter as HARNESS_ERROR. These staging commands are not the
finished whole-stack demo command. No full normal APIregression is claimed.

## Reports

Native original reports remain unchanged. Inspected fixture reports show correct
1total/0pass/1fail, nativeclass and component/moduleID. Their header embeds the
upstream DEPENDENCYgitmetadata, not componentimageprovenance, and longstacktraces
clip. Use project-owned report_summary.py and explicit deploymentprovenance next
to originals; never present nativeheadercommit as the tested productcommit.

See NEXT-MILESTONE.md and VERIFY-CONTRACT-AUDIT.md for the current unfinished
integration, sourcecontracts and required approval checkpoint before remote runs.

## Later local checkpoint

The optionalnativeS3 branch now has realMinIOlocalacceptance for BOTHcomponents,
with fakeHTTPsuite outcomes. Exactofficialsource+archivehash build_minio.py,
local_minio.py provenancecheck and tests/minio_native_acceptance.py reproduce it.
Earlier compiled-onlycaveat remains true historically, not currentlocalpath.
Combined prepare/runtimeentry and boundedproposal now exist; runtimeentryUNRUN.
See BOUNDED-RUN-PROPOSAL.md. Do not launch from these notes without review.
