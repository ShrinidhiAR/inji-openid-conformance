package inji.conformance;

import java.nio.file.*;
import java.lang.reflect.*;
import java.net.URI;
import java.util.*;
import io.mosip.testrig.apirig.testrunner.BaseTestCase;
import io.mosip.testrig.apirig.utils.ConfigManager;

/** Conformance-only mode INSIDE a pinned component api-test classpath.
 * Never calls native main/suiteSetup or general environment initialization.
 */
public final class IsolatedRigLauncher {
 public static void main(String[] args)throws Exception {
  String component=System.getProperty("conformance.component");
  if(!Set.of("certify","verify").contains(component))throw new IllegalArgumentException("component");
  Path root=Path.of(System.getProperty("user.dir")).toRealPath();
  if(!Files.readString(root.resolve(".conformance-isolated")).trim().equals("synthetic-conformance-only"))throw new IllegalArgumentException("isolated_marker");
  Path guardRoot=Path.of(System.getProperty("java.io.tmpdir")).toRealPath();
  if(!root.startsWith(guardRoot))throw new IllegalArgumentException("isolated_workdir_outside_temp");
  URI endpoint=URI.create(System.getProperty("env.endpoint"));
  if(!"https".equals(endpoint.getScheme()) || !(component+".local.test").equals(endpoint.getHost()) || endpoint.getPort()!=8443 || endpoint.getUserInfo()!=null || endpoint.getRawQuery()!=null || endpoint.getRawFragment()!=null || !(endpoint.getPath().isEmpty() || endpoint.getPath().equals("/")))throw new IllegalArgumentException("isolated_endpoint");
  Path suites=root.resolve("testNgXmlFiles");
  try(var paths=Files.list(suites)) {
   var files=paths.toList();
   if(files.size()!=1 || !files.get(0).getFileName().toString().equals("conformanceMasterTestSuite.xml"))throw new IllegalArgumentException("suite_scope");
   String expected="<suite name=\"Isolated native api-test conformance suite\"><listeners><listener class-name=\"io.mosip.testrig.apirig.report.EmailableReport\"/></listeners><test name=\"Official conformance outcomes\"><classes><class name=\"inji.conformance.OpenIDConformanceTest\"/></classes></test></suite>";
   if(!Files.readString(files.get(0)).replaceAll(">\\s+<","><").trim().equals(expected))throw new IllegalArgumentException("suite_contract");
   var parser=javax.xml.parsers.DocumentBuilderFactory.newInstance();parser.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
   var xml=parser.newDocumentBuilder().parse(files.get(0).toFile());
   var classes=xml.getElementsByTagName("class");var listeners=xml.getElementsByTagName("listener");
   if(classes.getLength()!=1 || !((org.w3c.dom.Element)classes.item(0)).getAttribute("name").equals("inji.conformance.OpenIDConformanceTest") || listeners.getLength()!=1 || !((org.w3c.dom.Element)listeners.item(0)).getAttribute("class-name").equals("io.mosip.testrig.apirig.report.EmailableReport") || xml.getElementsByTagName("packages").getLength()!=0 || xml.getElementsByTagName("suite-files").getLength()!=0)throw new IllegalArgumentException("suite_contract");
  }
  String prefix="io.inji.testrig.apirig.inji"+component;
  String runnerName=prefix+".testrunner.InjiTestRunner";
  Class<?> runner=Class.forName(runnerName);
  if(!runner.getMethod("getRunType").invoke(null).equals("IDE"))throw new IllegalStateException("isolated_mode_requires_compiled_classes_not_fatjar");
  Map<String,Object> props=new HashMap<>();props.put("push-reports-to-s3","no");props.put("mountPathForReport",root.resolve("testng-report").toString());props.put("useCaseToExecute","");props.put("slack-webhook-url","");
  String s3File=System.getProperty("conformance.localS3.properties");
  if(s3File!=null) {
   Path secrets=Path.of(s3File).toRealPath();if(!secrets.startsWith(guardRoot))throw new IllegalArgumentException("private_s3_config_path");
   Properties local=new Properties();try(var in=Files.newInputStream(secrets)){local.load(in);}
   URI s3=URI.create(local.getProperty("s3-host"));
   if(!Set.of("127.0.0.1","localhost","minio.local.test").contains(s3.getHost()) || !Set.of("http","https").contains(s3.getScheme()) || !"automationtests".equals(local.getProperty("s3-account")))throw new IllegalArgumentException("isolated_s3_endpoint");
   for(String key:List.of("s3-host","s3-region","s3-account","s3-user-key","s3-user-secret")) {String value=local.getProperty(key);if(value==null || value.isBlank())throw new IllegalArgumentException("local_s3_config_missing");props.put(key,value);}
   props.put("push-reports-to-s3","yes");props.put("reportExpirationInDays","1");
  }
  ConfigManager.init(props);
  // ConfigManager applies environment overrides: revalidate the effective values.
  if(!ConfigManager.getSlackWebHookUrl().isBlank())throw new IllegalArgumentException("external_notification_disallowed");
  if(s3File==null && !"no".equalsIgnoreCase(ConfigManager.getPushReportsToS3()))throw new IllegalArgumentException("unapproved_s3_override");
  if(s3File!=null) {
   URI effective=URI.create(ConfigManager.getS3Host());
   for(var address:java.net.InetAddress.getAllByName(effective.getHost()))if(!address.isLoopbackAddress())throw new IllegalArgumentException("local_s3_requires_loopback");
   if(!Set.of("127.0.0.1","localhost","minio.local.test").contains(effective.getHost()) || !"automationtests".equals(ConfigManager.getS3Account()))throw new IllegalArgumentException("effective_s3_endpoint_disallowed");
  }
  // Context labels only. No BaseTestCase.initialize or module ConfigManager.init.
  BaseTestCase.environment="isolated.synthetic.test";BaseTestCase.testLevel="conformance";BaseTestCase.currentModule="inji"+component;
  System.setProperty("benchmark.allowWarnings","false");
  System.setProperty("env.user","conformance-test");System.setProperty("modules","inji"+component);System.setProperty("emailable.report2.name","isolated-"+component+"-report.html");
  runner.getMethod("startTestRunner").invoke(null);
  if(s3File!=null)verifyLocalUploads(root,component);
  // Native runner's own exitcode is not used. Require TestNG XML counts.
  Path report=root.resolve("testng-report/testng-results.xml");
  var factory=javax.xml.parsers.DocumentBuilderFactory.newInstance();factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
  var result=factory.newDocumentBuilder().parse(report.toFile()).getDocumentElement();
  int total=Integer.parseInt(result.getAttribute("total")),failed=Integer.parseInt(result.getAttribute("failed")),skipped=Integer.parseInt(result.getAttribute("skipped"));
  int configurationFailures=result.getElementsByTagName("test-method").getLength();
  for(int i=0;i<configurationFailures;i++){var method=(org.w3c.dom.Element)result.getElementsByTagName("test-method").item(i);if("true".equals(method.getAttribute("is-config")) && !"PASS".equals(method.getAttribute("status")))System.exit(1);}
  if(total==0 || failed!=0 || skipped!=0)System.exit(1);
 }
 static void verifyLocalUploads(Path root,String component)throws Exception {
  var credentials=new com.amazonaws.auth.BasicAWSCredentials(ConfigManager.getS3UserKey(),ConfigManager.getS3SecretKey());
  var settings=new com.amazonaws.ClientConfiguration().withMaxErrorRetry(0).withConnectionTimeout(3000).withSocketTimeout(5000);
  var client=com.amazonaws.services.s3.AmazonS3ClientBuilder.standard().withCredentials(new com.amazonaws.auth.AWSStaticCredentialsProvider(credentials)).withClientConfiguration(settings).enablePathStyleAccess().withEndpointConfiguration(new com.amazonaws.client.builder.AwsClientBuilder.EndpointConfiguration(ConfigManager.getS3Host(),ConfigManager.getS3Region())).build();
  int checked=0;
  try(var files=Files.list(root.resolve("testng-report"))) {
   for(Path file:files.filter(p->p.getFileName().toString().endsWith(".html") && p.getFileName().toString().contains("-report_")).toList()) {
    String object="inji"+component+"/"+file.getFileName();
    try(var response=client.getObject("automationtests",object);var body=response.getObjectContent()) {
     byte[] expected=java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file));
     byte[] actual=java.security.MessageDigest.getInstance("SHA-256").digest(body.readAllBytes());
     if(!Arrays.equals(expected,actual))throw new IllegalStateException("report_upload_hash_mismatch");checked++;
    }
   }
  }finally{client.shutdown();}
  if(checked<2)throw new IllegalStateException("report_upload_incomplete");
  Files.writeString(root.resolve("local-s3-receipt.json"),"{\"scope\":\"isolated local automationtests bucket\",\"native_report_hashes_verified\":"+checked+"}");
 }

}
