package inji.conformance;

import java.nio.file.*;
import java.time.*;
import java.util.*;
import org.testng.annotations.BeforeSuite;

/** Runs fresh official conformance before the inherited per-module TestNG mapping. */
public final class OpenIDConformanceTest extends ConformanceResultsTest {
 @BeforeSuite(alwaysRun=true)
 public void invokeConformanceRunner()throws Exception {
  Path manifest=Path.of(System.getProperty("conformance.invocation")).toRealPath();
  var json=new org.json.JSONObject(Files.readString(manifest));
  String endpoint=System.getProperty("env.endpoint"),component=System.getProperty("conformance.component");
  if(!endpoint.equals(json.getString("env_endpoint")) || !component.equals(json.getString("component")))throw new IllegalArgumentException("invocation_environment_mismatch");
  var config=new org.json.JSONObject(Files.readString(Path.of(json.getString("config"))));
  if(component.equals("certify") && !endpoint.equals(config.getJSONObject("vci").getString("credential_issuer_url")))throw new IllegalArgumentException("issuer_endpoint_mismatch");
  if(component.equals("verify") && !endpoint.equals(json.getString("verify_service_url")))throw new IllegalArgumentException("verifier_endpoint_mismatch");
  java.net.URI suite=java.net.URI.create(json.getString("suite_url"));
  boolean fixture=Boolean.getBoolean("conformance.fixtureOnly");
  if(fixture){if(!"http".equals(suite.getScheme()) || !"127.0.0.1".equals(suite.getHost()))throw new IllegalArgumentException("fixture_suite_endpoint");}
  else if(!"https".equals(suite.getScheme()) || !"suite".equals(suite.getHost()) || suite.getPort()!=8443)throw new IllegalArgumentException("isolated_suite_endpoint");
  if(suite.getUserInfo()!=null || suite.getRawQuery()!=null || suite.getRawFragment()!=null || !suite.getPath().isEmpty())throw new IllegalArgumentException("suite_origin_contract");
  Path results=Path.of(System.getProperty("conformance.results")).toAbsolutePath();
  Files.deleteIfExists(results);
  List<String> command=new ArrayList<>();command.add("python3");command.add(json.getString("runner"));
  command.addAll(List.of("--component",component,"--base-url",json.getString("suite_url"),"--ca-file",json.getString("ca_file"),"--"+component+"-config",json.getString("config"),"--"+component+"-variants",json.getString("variants"),"--output",results.toString(),"--run-id",json.getString("run_id")));
  if(json.optBoolean("synthetic_handoffs",false))command.addAll(List.of("--synthetic-handoffs","--evidence-dir",json.getString("evidence_dir")));
  if(json.has("module"))command.addAll(List.of("--module",json.getString("module")));
  Process process=new ProcessBuilder(command).redirectOutput(ProcessBuilder.Redirect.DISCARD).redirectError(ProcessBuilder.Redirect.DISCARD).start();
  if(!process.waitFor(15,java.util.concurrent.TimeUnit.MINUTES)){process.destroyForcibly();throw new IllegalStateException("runner_timeout");}
  if(process.exitValue()>1 || !Files.exists(results))throw new IllegalStateException("runner_setup_failure");
  var document=new org.json.JSONObject(Files.readString(results));var run=document.getJSONObject("run");
  if(!json.getString("run_id").equals(run.getString("id")) || Instant.parse(run.getString("started_at")).isAfter(Instant.now().plusSeconds(10)) || Duration.between(Instant.parse(run.getString("started_at")),Instant.now()).toMinutes()>15)throw new IllegalStateException("freshness_failure");
 }
}
