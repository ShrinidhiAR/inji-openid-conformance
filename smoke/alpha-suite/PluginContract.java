import io.mosip.certify.util.KeyPairAndCertificateExtractor;import io.mosip.certify.mock.integration.mocks.MdocGenerator;import java.util.*;import java.nio.file.*;
public class PluginContract{
 public static void main(String[] a)throws Exception{
  String raw=Files.readString(Path.of(a[0]));String value=raw.lines().filter(x->x.startsWith("mosip.certify.mock.mdoc.issuer-key-cert=")).findFirst().get().split("=",2)[1];
  var pair=new KeyPairAndCertificateExtractor().extract(value);if(pair==null||pair.certificate().getIssuerX500Principal().equals(pair.certificate().getSubjectX500Principal()))throw new AssertionError("leaf extraction");
  Map<String,Object>data=new HashMap<>();data.put("family_name","Synthetic");data.put("given_name","Fixture");data.put("birth_date","1990-01-01");data.put("issuing_country","IN");data.put("document_number","SYNTHETIC-TEST");data.put("driving_privileges",new HashMap<String,String>(){{put("vehicle_category_code","A");}});
  String credential=new MdocGenerator().generate(data,a[1],value);Files.writeString(Path.of(a[2]),credential);System.out.println("PASS actual published plugin generator accepts CA-issued leaf input");
 }
}
