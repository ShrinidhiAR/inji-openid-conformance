package inji.conformance;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import org.json.JSONArray;
import org.json.JSONObject;
import org.testng.Assert;
import org.testng.Reporter;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

import io.mosip.testrig.apirig.dto.TestCaseDTO;

/**
 * Emits every OpenID conformance-suite module result as one TestNG result, so the
 * outcomes land in the api-testrig's normal TestNG/EmailableReport report. Each row
 * carries a TestCaseDTO as its first parameter, exactly like the rig's own
 * yml-driven tests, so module names and conformance-suite test ids show up in the
 * same columns of the same report.
 *
 * Input: the JSON written by scripts/conformance_runner.py:
 *   { "certify": [ {"module": ..., "test_id": ..., "status": ..., "result": ...}, ... ],
 *     "verify":  [ ... ] }
 *
 * Selection and policies are system properties, set by ConformanceBridgeRunner:
 *   conformance.results      path to the JSON file
 *   conformance.component    certify | verify | combined
 *   benchmark.allowWarnings  "true" (default): a WARNING counts as a pass with a review
 *                            note in the report; "false": WARNING fails the test.
 *
 * Benchmark semantics are a configurable project policy. The problem statement asks
 * for benchmark gating but states no numeric benchmark, so nothing here claims an
 * official MOSIP pass bar. The gate is fail-closed: FAILED, REVIEW, missing or
 * unknown results, and an empty result set, never count as passing.
 */
public class ConformanceResultsTest {

    /** One module outcome from the runner's JSON. */
    static final class ModuleOutcome {
        final String component;
        final String module;
        final String testId;
        final String status;
        final String result;

        ModuleOutcome(String component, String module, String testId, String status, String result) {
            this.component = component;
            this.module = module;
            this.testId = testId;
            this.status = status;
            this.result = result;
        }
    }

    @DataProvider(name = "conformanceModules")
    public Object[][] conformanceModules() throws IOException {
        String path = System.getProperty("conformance.results", "conformance-results.json");
        String component = System.getProperty("conformance.component", "combined");
        List<ModuleOutcome> selected = load(path, component);
        if (selected.isEmpty()) {
            // Fail-closed: one row that always fails, so an empty or missing result set
            // can never look like a green conformance run.
            selected = List.of(new ModuleOutcome(component, "(no conformance results found)", "-", "NONE", "NONE"));
        }
        Object[][] rows = new Object[selected.size()][];
        for (int i = 0; i < selected.size(); i++) {
            ModuleOutcome outcome = selected.get(i);
            TestCaseDTO testCase = new TestCaseDTO();
            testCase.setTestCaseName(outcome.module);
            testCase.setDescription(outcome.module);
            testCase.setUniqueIdentifier(outcome.component + " / conformance-test-id: " + outcome.testId);
            rows[i] = new Object[] { testCase, outcome };
        }
        return rows;
    }

    static List<ModuleOutcome> load(String path, String component) throws IOException {
        List<ModuleOutcome> out = new ArrayList<>();
        JSONObject root = new JSONObject(Files.readString(Path.of(path), StandardCharsets.UTF_8));
        List<String> components = switch (component) {
            case "certify", "verify" -> List.of(component);
            default -> List.of("certify", "verify"); // combined
        };
        for (String comp : components) {
            JSONArray arr = root.optJSONArray(comp);
            if (arr == null) {
                continue;
            }
            for (int i = 0; i < arr.length(); i++) {
                JSONObject m = arr.getJSONObject(i);
                out.add(new ModuleOutcome(comp, m.optString("module", "(unnamed module)"),
                        m.optString("test_id", "-"), m.optString("status", ""), m.optString("result", "")));
            }
        }
        return out;
    }

    @Test(dataProvider = "conformanceModules")
    public void conformanceModuleMustPass(TestCaseDTO testCase, ModuleOutcome outcome) {
        Reporter.getCurrentTestResult().setAttribute("TestCaseName", outcome.module);
        if ("NONE".equals(outcome.status)) {
            Assert.fail("No conformance results found for component '" + outcome.component
                    + "'. Nothing was executed, so the benchmark cannot be satisfied. "
                    + "Run scripts/conformance_runner.py first and point conformance.results at its output.");
        }
        switch (outcome.result) {
            case "PASSED" -> {
                // pass
            }
            case "WARNING" -> {
                boolean allowWarnings = Boolean.parseBoolean(
                        System.getProperty("benchmark.allowWarnings", "true"));
                if (allowWarnings) {
                    Reporter.log("WARNING from the conformance suite for module " + outcome.module
                            + " (status " + outcome.status + "). Counted as pass under the project policy "
                            + "benchmark.allowWarnings=true; review this module manually.", true);
                } else {
                    Assert.fail("Conformance suite reported WARNING for module " + outcome.module
                            + " and benchmark.allowWarnings=false, so this counts as a failure.");
                }
            }
            case "FAILED" -> Assert.fail("Conformance suite reported FAILED for module " + outcome.module
                    + " (status " + outcome.status + ").");
            default -> Assert.fail("Module " + outcome.module + " did not record a passing result "
                    + "(status=" + printable(outcome.status) + ", result=" + printable(outcome.result) + "). "
                    + "Only PASSED" + (Boolean.parseBoolean(System.getProperty("benchmark.allowWarnings", "true"))
                            ? " or WARNING" : "")
                    + " can satisfy the benchmark; everything else fails it.");
        }
    }

    private static String printable(String value) {
        return value == null || value.isBlank() ? "(none)" : value;
    }
}
