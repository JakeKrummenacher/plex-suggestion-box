from flask import Flask, render_template, request, redirect, url_for, session
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'jakeyboydog'


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        search_type = request.form.get("type")
        title = request.form.get("title")
        season = request.form.get("season")
        episode = request.form.get("episode")
        return redirect(url_for("process_title", type=search_type, title=title, season=season, episode=episode))
    return render_template("index.html")


def search_piratebay(query, filter_x265=True):
    base_url = "https://thepiratebay10.xyz/search/"
    search_query = f"{query} x265" if filter_x265 else query
    url = base_url + requests.utils.quote(search_query)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", id="searchResult")
    results = []

    if not table:
        print("No table found")
        return []

    rows = table.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        type_tag = cells[0].find("a", href=True, title=True)
        title_tag = cells[1].find("a", href=True, title=True)
        magnet_link = row.find("a", title="Download this torrent using magnet")
        size = cells[4]

        if title_tag and magnet_link and size and not type_tag.get_text(strip=True).__contains__("Porn"):
            title = title_tag.get_text(strip=True)
            magnet = magnet_link['href']
            size = size.get_text(strip=True)
            results.append({"title": title, "magnet": magnet, "size": size})

    print(f"Found {len(results)} torrents.")
    return results


def add_torrent_to_qbittorrent(magnet_link, media_type):
    qb_url = "http://plex:8080"
    add_url = f"{qb_url}/api/v2/torrents/add"

    if media_type == "movie":
        save_path = r"D:\Feature Films"
    elif media_type == "tv":
        save_path = r"D:\TV Shows\Unorganized"
    else:
        save_path = r"D:\Downloads"

    data = {
        "urls": magnet_link,
        "savepath": save_path,
        "autoTMM": "false",
        "paused": "false", 
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": qb_url,
    }

    response = requests.post(add_url, data=data, headers=headers)

    if response.status_code == 200:
        print(f"Successfully added torrent to {save_path}: {magnet_link}")
        return True
    else:
        print(f"Failed to add torrent. Status code: {response.status_code}, Response: {response.text}")
        return False


def add_to_qb(magnet_link, media_type):
    return add_torrent_to_qbittorrent(magnet_link, media_type)




@app.route("/process/<type>/<title>/", defaults={"season": None, "episode": None})
@app.route("/process/<type>/<title>/<season>/", defaults={"episode": None})
@app.route("/process/<type>/<title>/<season>/<episode>")
def process_title(type, title, season, episode):
    if type == "tv" and season and not episode:
        season = f"S{int(season):02d}"
        search_query = f"{title} {season}"
    elif type == "tv" and season and episode:
        season_episode = f"S{int(season):02d}E{int(episode):02d}"
        search_query = f"{title} {season_episode}"
    else:
        search_query = title

    results = search_piratebay(search_query, filter_x265=True)
    if not results:
        results = search_piratebay(search_query, filter_x265=False)

    if not results:
        return render_template("message.html", title="No Results Found", message="No torrents found for your search."), 404


    top_results = results[:10]
    session['results'] = top_results
    session['media_type'] = type

    return render_template("results.html", results=top_results)



@app.route("/select", methods=["POST"])
def select_torrent():
    selected_index = request.form.get("selected")
    if selected_index is None:
        return render_template("message.html", title="Selection Error", message="No selection was made."), 400
    
    try:
        selected_index = int(selected_index)
    except ValueError:
        return render_template("message.html", title="Invalid Selection", message="Your selection is not valid."), 400

    results = session.get("results")
    media_type = session.get("media_type", "movie")

    if not results or selected_index >= len(results):
        return render_template("message.html", title="Selection Out of Range", message="Your selection is out of range."), 400

    selected_torrent = results[selected_index]

    if add_to_qb(selected_torrent["magnet"], media_type):
        return render_template("message.html", title="Success", message="Torrent successfully added to qBittorrent!")
    else:
        return render_template("message.html", title="Failure", message="Failed to add torrent to qBittorrent."), 500



if __name__ == "__main__":
    app.run(debug=True, port=8000, host='0.0.0.0')
