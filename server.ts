import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Gjini Gartenbau – Hochwertige Gärten in Niederlenz AG" },
      { name: "description", content: "Seit 1997 gestalten wir einzigartige Gärten mit Leidenschaft, Präzision und handwerklicher Qualität. Familienunternehmen aus Niederlenz AG." },
      { name: "theme-color", content: "#23412D" },
      { property: "og:title", content: "Gjini Gartenbau – Hochwertige Gärten in Niederlenz AG" },
      { property: "og:description", content: "Seit 1997 gestalten wir einzigartige Gärten mit Leidenschaft, Präzision und handwerklicher Qualität. Familienunternehmen aus Niederlenz AG." },
      { property: "og:type", content: "website" },
      { property: "og:site_name", content: "Gjini Gartenbau" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:title", content: "Gjini Gartenbau – Hochwertige Gärten in Niederlenz AG" },
      { name: "twitter:description", content: "Seit 1997 gestalten wir einzigartige Gärten mit Leidenschaft, Präzision und handwerklicher Qualität. Familienunternehmen aus Niederlenz AG." },
      { property: "og:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/54afbf5d-ef91-4163-b432-1b0658b18839/id-preview-554f5a35--99e42f35-c711-4e57-a8e1-ad22f3ad1612.lovable.app-1782226586458.png" },
      { name: "twitter:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/54afbf5d-ef91-4163-b432-1b0658b18839/id-preview-554f5a35--99e42f35-c711-4e57-a8e1-ad22f3ad1612.lovable.app-1782226586458.png" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@300;400;500;600;700&display=swap",
      },
    ],
    scripts: [
      {
        type: "application/ld+json",
        children: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "LocalBusiness",
          name: "Gjini Gartenbau",
          telephone: "+41 62 891 36 23",
          address: {
            "@type": "PostalAddress",
            streetAddress: "Blumenweg 6",
            postalCode: "5702",
            addressLocality: "Niederlenz",
            addressRegion: "AG",
            addressCountry: "CH",
          },
          areaServed: "Kanton Aargau",
          priceRange: "$$",
        }),
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <Outlet />
    </QueryClientProvider>
  );
}
