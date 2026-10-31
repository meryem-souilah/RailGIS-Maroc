const API_BASE_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : `${window.location.protocol}//${window.location.hostname}:8000`;

const STATIC_FALLBACK = {
  lignes: "../data/processed/lignes.geojson",
  gares: "../data/processed/gares.geojson",
  regions: "../data/processed/regions.geojson",
  voiesOsm: "../data/processed/voies_osm.geojson",
};

const COULEURS_LIGNE = {
  LGV: "#c0392b",
  classique: "#2980b9",
  navette: "#e67e22",
};

const map = L.map("map").setView([31.5, -6.5], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 18,
}).addTo(map);

L.control.scale({ metric: true, imperial: false, position: "bottomleft" }).addTo(map);

let lignesGeojson = null;
let garesGeojson = null;
let lignesLayer = null;
let garesLayer = null;
let regionsLayer = null;
let heatLayer = null;
let osmLayer = null;

async function fetchJson(apiPath, fallbackPath) {
  try {
    const res = await fetch(`${API_BASE_URL}${apiPath}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`API indisponible (${apiPath}), utilisation du GeoJSON statique.`, err);
    const res = await fetch(fallbackPath);
    return await res.json();
  }
}

function styleLigne(feature) {
  return {
    color: COULEURS_LIGNE[feature.properties.type_ligne] || "#7f8c8d",
    weight: 3,
    opacity: 0.85,
  };
}

function garePointToLayer(feature, latlng) {
  return L.circleMarker(latlng, {
    radius: 5,
    fillColor: "#2c3e50",
    color: "#fff",
    weight: 1,
    fillOpacity: 0.9,
  });
}

async function afficherHorairesGare(gareId, gareNom) {
  const panel = document.getElementById("info-gare");
  const contenu = document.getElementById("info-gare-contenu");
  panel.hidden = false;
  contenu.innerHTML = "<em>Chargement...</em>";

  try {
    const res = await fetch(`${API_BASE_URL}/gares/${encodeURIComponent(gareId)}/horaires`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.horaires.length) {
      contenu.innerHTML = `<strong>${gareNom}</strong><p>Aucun horaire trouve.</p>`;
      return;
    }

    const rows = data.horaires
      .slice(0, 15)
      .map(
        (h) => `<tr><td>${h.ligne_id}</td><td>${h.heure_depart}</td><td>${h.heure_arrivee}</td></tr>`
      )
      .join("");

    contenu.innerHTML = `
      <strong>${gareNom}</strong>
      <p>${data.nb_passages} passage(s)</p>
      <table>
        <thead><tr><th>Ligne</th><th>Depart</th><th>Arrivee</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (err) {
    contenu.innerHTML = `<strong>${gareNom}</strong><p>Horaires indisponibles (API hors service).</p>`;
  }
}

function appliquerFiltres() {
  const typesActifs = Array.from(document.querySelectorAll(".filtre-type:checked")).map(
    (el) => el.value
  );
  const regionActive = document.getElementById("filtre-region").value;

  if (lignesLayer) {
    lignesLayer.eachLayer((layer) => {
      const visible = typesActifs.includes(layer.feature.properties.type_ligne);
      layer.setStyle({ opacity: visible ? 0.85 : 0, weight: visible ? 3 : 0 });
    });
  }

  if (garesLayer) {
    garesLayer.eachLayer((layer) => {
      const regionOk = !regionActive || layer.feature.properties.region_id === regionActive;
      const el = layer.getElement ? layer.getElement() : null;
      layer.setStyle({ opacity: regionOk ? 1 : 0, fillOpacity: regionOk ? 0.9 : 0 });
    });
  }
}

function peuplerFiltreRegions() {
  const select = document.getElementById("filtre-region");
  const regions = new Map();
  garesGeojson.features.forEach((f) => {
    if (f.properties.region_id) {
      regions.set(f.properties.region_id, f.properties.region_id);
    }
  });
  regions.forEach((_, id) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    select.appendChild(opt);
  });
}

function couleurChoroplethe(nbGares, maxGares) {
  if (!maxGares) return "#fee8c8";
  const t = Math.min(nbGares / maxGares, 1);
  // interpolation lineaire entre jaune pale (#fee8c8) et rouge brique (#e34a33)
  const lerp = (a, b) => Math.round(a + (b - a) * t);
  return `rgb(${lerp(254, 227)}, ${lerp(232, 74)}, ${lerp(200, 51)})`;
}

async function activerChoroplethe() {
  if (!regionsLayer) {
    const regionsGeojson = await fetchJson("/regions", STATIC_FALLBACK.regions);
    const maxGares = Math.max(...regionsGeojson.features.map((f) => f.properties.nb_gares || 0), 1);
    regionsLayer = L.geoJSON(regionsGeojson, {
      style: (feature) => ({
        color: "#999",
        weight: 1,
        fillColor: couleurChoroplethe(feature.properties.nb_gares || 0, maxGares),
        fillOpacity: 0.6,
      }),
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        layer.bindTooltip(`${p.nom} : ${p.nb_gares} gare(s)`);
      },
    });
  }
  regionsLayer.addTo(map);
  regionsLayer.bringToBack();
  document.getElementById("legende-choroplethe").hidden = false;
}

function desactiverChoroplethe() {
  if (regionsLayer) map.removeLayer(regionsLayer);
  document.getElementById("legende-choroplethe").hidden = true;
}

async function activerHeatmap() {
  if (!heatLayer) {
    const points = garesGeojson.features.map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      return [lat, lon, Math.max(f.properties.nb_passages || 0, 1)];
    });
    heatLayer = L.heatLayer(points, { radius: 30, blur: 20, max: 12, minOpacity: 0.35 });
  }
  heatLayer.addTo(map);
}

function desactiverHeatmap() {
  if (heatLayer) map.removeLayer(heatLayer);
}

async function activerOsm() {
  if (!osmLayer) {
    const osmGeojson = await fetchJson("/lignes/osm", STATIC_FALLBACK.voiesOsm);
    osmLayer = L.geoJSON(osmGeojson, { style: { color: "#555", weight: 1.5, opacity: 0.7 } });
  }
  osmLayer.addTo(map);
}

function desactiverOsm() {
  if (osmLayer) map.removeLayer(osmLayer);
}

function telechargerGeojson(data, nomFichier) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/geo+json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomFichier;
  a.click();
  URL.revokeObjectURL(url);
}

async function init() {
  [lignesGeojson, garesGeojson] = await Promise.all([
    fetchJson("/lignes", STATIC_FALLBACK.lignes),
    fetchJson("/gares", STATIC_FALLBACK.gares),
  ]);

  lignesLayer = L.geoJSON(lignesGeojson, { style: styleLigne }).addTo(map);

  garesLayer = L.geoJSON(garesGeojson, {
    pointToLayer: garePointToLayer,
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      layer.bindPopup(
        `<strong>${p.nom}</strong><br/>` +
          `Region : ${p.region_id || "n/d"}<br/>` +
          `${p.nb_passages || 0} passage(s)/jour<br/>` +
          `<em>Cliquer sur la gare pour le detail des horaires</em>`
      );
      layer.on("click", () => afficherHorairesGare(p.id, p.nom));
    },
  }).addTo(map);

  const bounds = lignesLayer.getBounds();
  if (bounds.isValid()) map.fitBounds(bounds, { padding: [20, 20] });

  peuplerFiltreRegions();

  document.querySelectorAll(".filtre-type").forEach((el) => el.addEventListener("change", appliquerFiltres));
  document.getElementById("filtre-region").addEventListener("change", appliquerFiltres);
  document.getElementById("export-lignes").addEventListener("click", () => telechargerGeojson(lignesGeojson, "lignes.geojson"));
  document.getElementById("export-gares").addEventListener("click", () => telechargerGeojson(garesGeojson, "gares.geojson"));

  document.getElementById("couche-choroplethe").addEventListener("change", (e) => {
    if (e.target.checked) activerChoroplethe();
    else desactiverChoroplethe();
  });
  document.getElementById("couche-heatmap").addEventListener("change", (e) => {
    if (e.target.checked) activerHeatmap();
    else desactiverHeatmap();
  });
  document.getElementById("couche-osm").addEventListener("change", (e) => {
    if (e.target.checked) activerOsm();
    else desactiverOsm();
  });
}

init();
