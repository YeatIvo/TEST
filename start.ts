import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import heroImg from "@/assets/hero.jpg";
import { SiteHeader, SiteFooter, PageHero, CTASection } from "@/components/site";
import { processSteps } from "@/lib/site-data";

export const Route = createFileRoute("/ablauf")({
  head: () => ({
    meta: [
      { title: "Ablauf – Gjini Gartenbau" },
      { name: "description", content: "Von der Beratung über die Planung bis zur Umsetzung – so realisieren wir Ihren Garten in vier klaren Schritten." },
      { property: "og:title", content: "Ablauf – Gjini Gartenbau" },
      { property: "og:description", content: "Strukturierter Prozess für ein souveränes Ergebnis." },
      { property: "og:url", content: "/ablauf" },
    ],
    links: [{ rel: "canonical", href: "/ablauf" }],
  }),
  component: ProcessPage,
});

function ProcessPage() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <PageHero
        eyebrow="Ablauf"
        title="Von der ersten Idee bis zum fertigen Garten."
        subtitle="Ein klarer, transparenter Prozess – damit Sie sich auf das Wesentliche konzentrieren können: die Vorfreude auf Ihren Garten."
        image={heroImg}
      />

      <section className="py-24 md:py-32">
        <div className="container-page grid gap-10 md:grid-cols-4">
          {processSteps.map((s, i) => (
            <div key={s.n} className="relative rounded-lg border border-border bg-card p-7 transition hover:border-sage hover:shadow-soft">
              <div className="font-display text-5xl font-semibold text-sage">{s.n}</div>
              <div className="mt-4 h-px w-full bg-sage/30" />
              <h3 className="mt-5 font-display text-xl font-semibold">{s.t}</h3>
              <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">{s.d}</p>
              {i < processSteps.length - 1 && (
                <ArrowRight className="absolute -right-4 top-10 hidden h-5 w-5 text-sage md:block" />
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="bg-sand py-24 md:py-28">
        <div className="container-page max-w-3xl">
          <p className="eyebrow">Was Sie erwarten dürfen</p>
          <h2 className="mt-4 font-display text-3xl font-semibold leading-tight sm:text-4xl">
            Verbindlichkeit in jeder Phase.
          </h2>
          <ul className="mt-8 space-y-4 text-base text-muted-foreground md:text-lg">
            <li><strong className="text-primary">Transparente Angebote</strong> – nachvollziehbar kalkuliert, ohne versteckte Kosten.</li>
            <li><strong className="text-primary">Feste Ansprechperson</strong> – ein Kontakt von Anfang bis Übergabe.</li>
            <li><strong className="text-primary">Saubere Baustelle</strong> – Ordnung und Rücksicht auf Ihr Zuhause sind selbstverständlich.</li>
            <li><strong className="text-primary">Pflege auf Wunsch</strong> – wir begleiten Ihren Garten auch nach der Übergabe.</li>
          </ul>
        </div>
      </section>

      <CTASection />
      <SiteFooter />
    </div>
  );
}
