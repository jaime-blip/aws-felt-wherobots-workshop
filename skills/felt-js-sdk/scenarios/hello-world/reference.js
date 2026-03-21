import { Felt } from "@feltmaps/js-sdk";

const felt = await Felt.embed(
  document.getElementById("map-container"),
  "FELT_MAP_ID"
);

await felt.setViewport({
  center: { lat: 37.78, lng: -122.42 },
  zoom: 12
});
