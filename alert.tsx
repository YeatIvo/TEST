import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { Menu, X, Phone, Mail, MapPin, ArrowRight } from "lucide-react";
import logo from "@/assets/gjini-logo.png.asset.json";

const links = [
  { to: "/", label: "Start" },
  { to: "/ueber-uns", label: "Über uns" },
  { to: "/leistungen", label: "Leistungen" },
  { to: "/referenzen", label: "Referenzen" },
  { to: "/ablauf", label: "Ablauf" },
  { to: "/kontakt", label: "Kontakt" },
] as const;

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/85 backdrop-blur-xl">
      <div className="container-page flex h-16 items-center justify-between md:h-20">
        <Link to="/" className="flex items-center gap-3" onClick={() => setOpen(false)}>
          <img src={logo.url} alt="Gjini Gartenbau" width={120} height={72} className="h-8 w-auto md:h-10" />
        </Link>
        <nav className="hidden items-center gap-7 lg:flex">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              activeOptions={{ exact: l.to === "/" }}
              activeProps={{ className: "text-primary" }}
              inactiveProps={{ className: "text-foreground/75" }}
              className="text-sm font-medium transition hover:text-primary"
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <Link
          to="/kontakt"
          className="hidden rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 lg:inline-flex"
        >
          Beratung anfragen
        </Link>
        <button onClick={() => setOpen(!open)} className="lg:hidden" aria-label="Menü">
          {open ? <X className="h-6 w-6 text-primary" /> : <Menu className="h-6 w-6 text-primary" />}
        </button>
      </div>
      {open && (
        <div className="border-t border-border/60 bg-background lg:hidden">
          <div className="container-page flex flex-col gap-1 py-4">
            {links.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                onClick={() => setOpen(false)}
                activeOptions={{ exact: l.to === "/" }}
                activeProps={{ className: "text-primary" }}
                inactiveProps={{ className: "text-foreground/80" }}
                className="rounded-md px-2 py-3 text-base font-medium hover:bg-secondary"
              >
                {l.label}
              </Link>
            ))}
            <Link
              to="/kontakt"
              onClick={() => setOpen(false)}
              className="mt-2 rounded-full bg-primary px-5 py-3 text-center text-sm font-medium text-primary-foreground"
            >
              Beratung anfragen
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-card py-12">
      <div className="container-page grid gap-10 md:grid-cols-4">
        <div className="md:col-span-2">
          <img src={logo.url} alt="Gjini Gartenbau" width={120} height={72} className="h-12 w-auto" />
          <p className="mt-5 max-w-sm text-sm text-muted-foreground">
            Hochwertige Gartenarbeiten aus Niederlenz AG – seit 1997. Familienunternehmen mit Leidenschaft für Detail und Qualität.
          </p>
        </div>
        <div className="text-sm">
          <div className="font-medium text-primary">Navigation</div>
          <ul className="mt-3 space-y-2 text-muted-foreground">
            {links.slice(1).map((l) => (
              <li key={l.to}>
                <Link to={l.to} className="hover:text-primary">{l.label}</Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="text-sm">
          <div className="font-medium text-primary">Kontakt</div>
          <ul className="mt-3 space-y-2.5 text-muted-foreground">
            <li className="flex items-start gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0" /> Blumenweg 6, 5702 Niederlenz</li>
            <li className="flex items-start gap-2"><Phone className="mt-0.5 h-4 w-4 shrink-0" /> <a href="tel:+41628913623" className="hover:text-primary">062 891 36 23</a></li>
            <li className="flex items-start gap-2"><Phone className="mt-0.5 h-4 w-4 shrink-0" /> <a href="tel:+41792883535" className="hover:text-primary">079 288 35 35</a></li>
            <li className="flex items-start gap-2"><Mail className="mt-0.5 h-4 w-4 shrink-0" /> <a href="mailto:info@gjini-gartenbau.ch" className="hover:text-primary">info@gjini-gartenbau.ch</a></li>
          </ul>
        </div>
      </div>
      <div className="container-page mt-10 flex flex-col items-start justify-between gap-3 border-t border-border pt-6 text-xs text-muted-foreground md:flex-row">
        <p>© {new Date().getFullYear()} Gjini Gartenbau. Alle Rechte vorbehalten.</p>
        <p>Niederlenz · Aargau · Schweiz</p>
      </div>
    </footer>
  );
}

export function PageHero({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle?: string; image?: string }) {
  return (
    <section className="relative overflow-hidden border-b border-primary/15 bg-gradient-to-br from-primary via-primary to-forest text-primary-foreground">
      <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-sage/25 blur-3xl" />
      <div className="pointer-events-none absolute -left-32 bottom-[-6rem] h-80 w-80 rounded-full bg-sand/15 blur-3xl" />
      <div className="container-page relative py-12 md:py-16">
        <nav className="flex items-center gap-2 text-xs text-primary-foreground/70">
          <Link to="/" className="transition hover:text-primary-foreground">Start</Link>
          <span className="text-primary-foreground/30">/</span>
          <span className="text-primary-foreground">{eyebrow}</span>
        </nav>
        <div className="mt-8 grid items-end gap-6 md:grid-cols-12 md:gap-10">
          <div className="md:col-span-7">
            <p className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.28em] text-sand">
              <span className="h-px w-8 bg-sand/60" /> {eyebrow}
            </p>
            <h1 className="mt-4 font-display text-3xl font-semibold leading-[1.1] text-primary-foreground sm:text-4xl md:text-5xl">
              {title}
            </h1>
          </div>
          {subtitle && (
            <div className="md:col-span-5 md:border-l md:border-primary-foreground/20 md:pl-8">
              <p className="text-sm leading-relaxed text-primary-foreground/80 md:text-base">{subtitle}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export function CTASection() {
  return (
    <section className="bg-sand py-20 md:py-24">
      <div className="container-page flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
        <div className="max-w-xl">
          <h2 className="font-display text-3xl font-semibold leading-tight sm:text-4xl">
            Lassen Sie uns Ihren Traumgarten verwirklichen.
          </h2>
          <p className="mt-3 text-muted-foreground">Unverbindliches Beratungsgespräch – wir melden uns innert 24 Stunden.</p>
        </div>
        <Link
          to="/kontakt"
          className="inline-flex shrink-0 items-center gap-2 rounded-full bg-primary px-7 py-4 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
        >
          Kostenlose Beratung anfragen <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}
