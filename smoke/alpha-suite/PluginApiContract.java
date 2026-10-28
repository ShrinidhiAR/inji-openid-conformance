import net.openid.conformance.variant.*;
import com.google.gson.*;
import java.util.*;
public class PluginApiContract {
 public static void main(String[] args) {
  var service=new VariantService((java.util.function.Predicate<VariantService.TestPlanHolder>)(p->true));
  var holder=service.getTestPlan("oid4vci-1_0-issuer-test-plan");
  var gson=new GsonBuilder().setPrettyPrinting().create();
  var variants=new LinkedHashMap<String,String>();
  variants.put("fapi_profile","vci");variants.put("credential_format","mdoc");variants.put("authorization_request_type","simple");variants.put("client_auth_type","private_key_jwt");variants.put("fapi_request_method","unsigned");variants.put("sender_constrain","dpop");variants.put("vci_authorization_code_flow_variant","wallet_initiated");variants.put("vci_credential_encryption","plain");variants.put("vci_grant_type","authorization_code");
  var out=new LinkedHashMap<String,Object>();out.put("planName",holder.info.testPlanName());out.put("variants",holder.getVariantSummary());out.put("modules",holder.getTestModules());out.put("defaults",holder.getUnsetDefaults(new VariantSelection(variants)));out.put("selectedVariantModules",holder.getTestModulesForVariant(new VariantSelection(variants)));System.out.println(gson.toJson(out));
 }
}
