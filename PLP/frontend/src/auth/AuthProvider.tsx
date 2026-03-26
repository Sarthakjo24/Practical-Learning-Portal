import { PropsWithChildren } from "react";
import { Auth0Provider } from "@auth0/auth0-react";

const domain = import.meta.env.VITE_AUTH0_DOMAIN ?? "";
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID ?? "";
const audience = import.meta.env.VITE_AUTH0_AUDIENCE ?? "";

export function AppAuthProvider({ children }: PropsWithChildren) {
  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      cacheLocation="localstorage"
      authorizationParams={{
        redirect_uri: window.location.origin + "/dashboard",
        audience,
        scope: "openid profile email"
      }}
    >
      {children}
    </Auth0Provider>
  );
}
