import sGartenbau from "@/assets/s-gartenbau.jpg";
import sGestaltung from "@/assets/s-gestaltung.jpg";
import sPflege from "@/assets/s-pflege.jpg";
import sNaturstein from "@/assets/s-naturstein.jpg";
import sTerrasse from "@/assets/s-terrasse.jpg";
import sWasser from "@/assets/s-wasser.jpg";
import sZaun from "@/assets/s-zaun.jpg";
import sUmgebung from "@/assets/s-umgebung.jpg";
import rPrivat from "@/assets/r-privat.jpg";
import rTerrasse from "@/assets/r-terrasse.jpg";
import rStein from "@/assets/r-stein.jpg";
import rPflege from "@/assets/r-pflege.jpg";
import rWasser from "@/assets/r-wasser.jpg";
import rUmgebung from "@/assets/r-umgebung.jpg";

export const services = [
  { slug: "gartenbau", title: "Gartenbau", desc: "Vom ersten Spatenstich bis zur fertigen Anlage – wir realisieren Ihren Garten als komplettes Gesamtwerk.", img: sGartenbau },
  { slug: "gartengestaltung", title: "Gartengestaltung", desc: "Individuelle Konzepte, die Architektur, Landschaft und Lebensgefühl harmonisch verbinden.", img: sGestaltung },
  { slug: "gartenpflege", title: "Gartenpflege", desc: "Regelmässige Pflege, damit Ihr Garten über Jahre seine Schönheit und Struktur behält.", img: sPflege },
  { slug: "natursteinarbeiten", title: "Natursteinarbeiten", desc: "Mauern, Treppen und Wege aus Naturstein – handwerklich präzise verarbeitet.", img: sNaturstein },
  { slug: "terrassenbau", title: "Terrassenbau", desc: "Hochwertige Terrassen aus Holz, Stein oder Keramik – langlebig und stilvoll.", img: sTerrasse },
  { slug: "wasseranlagen", title: "Teich- & Wasseranlagen", desc: "Teiche, Quellen und Wasserspiele, die Ruhe und Atmosphäre in Ihren Garten bringen.", img: sWasser },
  { slug: "zaunbau", title: "Zaunbau", desc: "Sichtschutz und Einfriedungen aus Holz, Metall oder als lebendige Hecke.", img: sZaun },
  { slug: "umgebungsarbeiten", title: "Umgebungsarbeiten", desc: "Wege, Plätze, Beleuchtung und Bepflanzung rund um Ihr Zuhause oder Gewerbe.", img: sUmgebung },
];

export const projects = [
  { cat: "Privatgärten", img: rPrivat, title: "Residenz Aargau" },
  { cat: "Terrassen", img: rTerrasse, title: "Terrasse Lenzburg" },
  { cat: "Natursteinarbeiten", img: rStein, title: "Trockenmauer" },
  { cat: "Gartenpflege", img: rPflege, title: "Heckenarchitektur" },
  { cat: "Wasseranlagen", img: rWasser, title: "Quellteich" },
  { cat: "Umgebungsarbeiten", img: rUmgebung, title: "Eingangsbereich" },
];

export const projectCategories = ["Alle", "Privatgärten", "Terrassen", "Natursteinarbeiten", "Gartenpflege", "Wasseranlagen", "Umgebungsarbeiten"];

export const testimonials = [
  { text: "Von der Planung bis zur Fertigstellung hat alles perfekt funktioniert. Unser Garten ist wunderschön geworden.", name: "Familie M.", place: "Lenzburg" },
  { text: "Sehr zuverlässiges Team und hervorragende Arbeit. Wir empfehlen Gjini Gartenbau jederzeit weiter.", name: "S. Keller", place: "Wildegg" },
  { text: "Hohe Qualität, saubere Ausführung und freundliche Beratung – ein durchwegs professioneller Partner.", name: "Familie B.", place: "Niederlenz" },
];

export const processSteps = [
  { n: "01", t: "Beratung", d: "Persönliches Gespräch vor Ort, um Ihre Wünsche und Möglichkeiten zu klären." },
  { n: "02", t: "Planung", d: "Detaillierte Konzeption mit Visualisierung, Materialwahl und transparentem Angebot." },
  { n: "03", t: "Umsetzung", d: "Saubere, koordinierte Ausführung durch unser eingespieltes Team." },
  { n: "04", t: "Fertiges Projekt", d: "Übergabe Ihres Gartens – auf Wunsch mit langfristiger Pflege." },
];
