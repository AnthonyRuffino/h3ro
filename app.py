from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
import h3
import geojson
import csv
import io
from fastapi.responses import Response
import csv
import io
from fastapi import Body, Query
from shapely.geometry import shape, Polygon
import json


app = FastAPI()

def build_h3_ring_geojson(lat: float, lng: float, resolution: int, ring_k: int):
    try:
        center = h3.geo_to_h3(lat, lng, resolution)
        ring = h3.k_ring(center, ring_k)

        features = []
        for h in ring:
            boundary = h3.h3_to_geo_boundary(h, geo_json=True)
            features.append(geojson.Feature(
                geometry=geojson.Polygon([boundary]),
                properties={"h3_index": h}
            ))

        geojson_obj = geojson.FeatureCollection(features)
        return geojson.dumps(geojson_obj)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating H3 cells: {str(e)}")


@app.post("/h3-ring", response_class=PlainTextResponse)
async def h3_ring_post(request: Request):
    try:
        data = await request.json()
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
        resolution = int(data.get("resolution", 9))
        ring_k = int(data.get("ring_k", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or missing parameters: 'lat' and 'lng' must be numbers.")

    return build_h3_ring_geojson(lat, lng, resolution, ring_k)


@app.get("/h3-ring", response_class=PlainTextResponse)
async def h3_ring_get(
    lat: float = Query(...),
    lng: float = Query(...),
    resolution: int = Query(9),
    ring_k: int = Query(1)
):
    return build_h3_ring_geojson(lat, lng, resolution, ring_k)



@app.get("/h3-ring-csv", response_class=Response)
async def h3_ring_csv(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    resolution: int = Query(9, ge=0, le=15, description="H3 resolution (0–15)"),
    ring_k: int = Query(1, ge=0, le=10, description="Radius in hexagons (k-ring)")
):
    try:
        center = h3.geo_to_h3(lat, lng, resolution)
        ring = h3.k_ring(center, ring_k)

        # Write CSV to in-memory buffer
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["h3_index"])
        for h in ring:
            writer.writerow([h])

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=h3_ring.csv"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating H3 CSV: {str(e)}")




@app.post("/h3-ring-csv", response_class=Response)
async def h3_ring_csv_post(request: Request):
    try:
        data = await request.json()
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
        resolution = int(data.get("resolution", 9))
        ring_k = int(data.get("ring_k", 1))
    except (TypeError, ValueError, KeyError):
        raise HTTPException(status_code=400, detail="Missing or invalid parameters in POST body")

    try:
        center = h3.geo_to_h3(lat, lng, resolution)
        ring = h3.k_ring(center, ring_k)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["h3_index"])
        for h in ring:
            writer.writerow([h])

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=h3_ring.csv"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating H3 CSV: {str(e)}")







@app.post("/h3-polyfill-csv", response_class=Response)
async def h3_polyfill_csv(
    resolution: int = Query(..., ge=0, le=15, description="H3 resolution (0–15)"),
    interior: bool = Query(False, description="Only include H3 cells fully inside the polygon"),
    buffer: float = Query(0.0, ge=0.0, le=0.05, description="Buffer distance in degrees (applies only if interior=false)"),
    geojson_input: dict = Body(...)
):
    try:
        features = geojson_input.get("features", [])
        if not features:
            raise HTTPException(status_code=400, detail="GeoJSON must include at least one feature")

        # Use only first feature
        geometry = features[0]["geometry"]
        if geometry["type"] != "Polygon":
            raise HTTPException(status_code=400, detail="Only Polygon geometry is supported")

        polygon_coords = geometry["coordinates"]
        shapely_poly = Polygon(polygon_coords[0])

        if interior:
            # Use exact shape, then filter for strict containment
            h3_indexes = h3.polyfill({
                "type": "Polygon",
                "coordinates": polygon_coords
            }, resolution, geo_json_conformant=True)

            h3_indexes = {
                h for h in h3_indexes
                if shapely_poly.contains(Polygon(h3.h3_to_geo_boundary(h, geo_json=True)))
            }

        else:
            # Expand polygon slightly using buffer
            buffered_poly = shapely_poly.buffer(buffer)

            buffered_coords = list(buffered_poly.exterior.coords)

            h3_indexes = h3.polyfill({
                "type": "Polygon",
                "coordinates": [buffered_coords]
            }, resolution, geo_json_conformant=True)


        # Prepare CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["h3_index"])
        for h in sorted(h3_indexes):
            writer.writerow([h])

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=h3_polyfill.csv"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating H3 polyfill: {str(e)}")




