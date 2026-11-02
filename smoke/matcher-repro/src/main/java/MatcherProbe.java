import java.util.*;
import jakarta.servlet.*;
import java.lang.reflect.Proxy;
import org.springframework.security.config.annotation.web.AbstractRequestMatcherRegistry;
import org.springframework.security.config.annotation.ObjectPostProcessor;
import org.springframework.security.web.util.matcher.RequestMatcher;
import java.nio.file.*;
import org.springframework.mock.web.*;
import org.springframework.core.env.*;
import org.springframework.core.convert.support.DefaultConversionService;
import org.springframework.util.AntPathMatcher;
import org.springframework.security.web.servlet.util.matcher.MvcRequestMatcher;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.web.servlet.handler.HandlerMappingIntrospector;
import org.springframework.web.context.support.StaticWebApplicationContext;
public class MatcherProbe {
 static class Registry extends AbstractRequestMatcherRegistry<List<RequestMatcher>> {
  Registry(StaticWebApplicationContext c){setApplicationContext(c);}
  protected List<RequestMatcher> chainRequestMatchers(List<RequestMatcher> m){return m;}
 }
 static class RegisteredContext extends MockServletContext {
  public Map<String,? extends ServletRegistration> getServletRegistrations(){
   ServletRegistration r=(ServletRegistration)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{ServletRegistration.class},(proxy,method,args)->{
    return switch(method.getName()){
     case "getName" -> "dispatcherServlet";
     case "getClassName" -> "org.springframework.web.servlet.DispatcherServlet";
     case "getMappings" -> Set.of("/v1/certify/*");
     default -> null;
    };
   });
   return Map.of("dispatcherServlet",r);
  }
 }

 public static void main(String[] args)throws Exception {
  String key="mosip.certify.security.ignore-auth-urls";
  for(String file:args){
   Properties p=new Properties();try(var r=Files.newBufferedReader(Path.of(file))){p.load(r);}
   if(!p.containsKey(key))continue;
   StandardEnvironment env=new StandardEnvironment();env.setConversionService(new DefaultConversionService());env.getPropertySources().addFirst(new PropertiesPropertySource("file",p));
   String[] patterns=env.getProperty(key,String[].class);
   if(patterns[0].equals("/actuator/health"))patterns[0]="**/actuator/**";
   System.out.println("FILE="+file+" patterns="+Arrays.toString(patterns));
   MockServletContext sc=new RegisteredContext();
   StaticWebApplicationContext context=new StaticWebApplicationContext();context.setServletContext(sc);context.refresh();
   HandlerMappingIntrospector intro=new HandlerMappingIntrospector();intro.setApplicationContext(context);intro.afterPropertiesSet();
   context.getBeanFactory().registerSingleton("mvcHandlerMappingIntrospector",intro);
   context.getBeanFactory().registerSingleton("objectPostProcessor",new ObjectPostProcessor<Object>(){public <O> O postProcess(O o){return o;}});
   MockHttpServletRequest request=new MockHttpServletRequest(sc,"GET","/v1/certify/actuator/health");request.setServletPath("/v1/certify");request.setPathInfo("/actuator/health");
   boolean any=false;
   for(String pattern:patterns){MvcRequestMatcher m=new MvcRequestMatcher(intro,pattern);m.setServletPath("/v1/certify");boolean match=m.matches(request);any|=match;if(pattern.contains("actuator")) System.out.println("original="+pattern+" mvc="+match+" ant="+new AntPathRequestMatcher(pattern).matches(request));}
   System.out.println("any configured MVC exclusion="+any);
   var resolved=new Registry(context).requestMatchers(patterns);
   System.out.println("REGISTRY actual path servlet=/v1/certify/* resolved="+resolved.get(0).getClass().getName()+" any="+resolved.stream().anyMatch(x->x.matches(request)));
   String[] repaired=patterns.clone();
   if(!repaired[0].equals("**/actuator/**"))throw new AssertionError("unexpected baseline");
   repaired[0]="/actuator/health";
   var narrow=new Registry(context).requestMatchers(repaired);
   int passed=0;
   for(String path:new String[]{"/actuator/health","/actuator/env","/actuator/configprops","/actuator/health/db","/actuator","/actuator/health/","/actuator/healthcheck","/credential-configurations","/.well-known/openid-credential-issuer","/nonce","/issuance/credential","/oauth/token","/system-info","/admin"}){
    MockHttpServletRequest r=new MockHttpServletRequest(sc,"GET","/v1/certify"+path);r.setServletPath("/v1/certify");r.setPathInfo(path);
    boolean before=resolved.stream().anyMatch(x->x.matches(r));
    boolean after=narrow.stream().anyMatch(x->x.matches(r));
    if(path.equals("/actuator/health")){if(before||!after)throw new AssertionError(path);}
    else if(before!=after)throw new AssertionError("unrelated exposure changed: "+path);
    System.out.println("GET "+path+" before="+before+" after="+after);passed++;
   }
   System.out.println("PASS narrow health-only delta: "+passed+" cases");
   context.close();
  }
 }
}
