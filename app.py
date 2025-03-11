from flask import Flask, render_template, request, redirect, url_for, session
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'jakeyboydog'


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Render the homepage or process the search form submission.
    """
    if request.method == "POST":
        # Retrieve search parameters from the form
        search_type = request.form.get("type")
        title = request.form.get("title")
        season = request.form.get("season")
        episode = request.form.get("episode")
        return redirect(url_for("process_title", type=search_type, title=title, season=season, episode=episode))
    return render_template("index.html")


def search_piratebay(query, type, filter_h265, filter_x265=True):
    """
    Search The Pirate Bay for torrents based on the query and codec filters.

    Parameters:
        query (str): The base search term.
        type (str): Media type ('movie' or 'tv') to determine the search suffix.
        filter_h265 (bool): Whether to apply the h265 codec filter.
        filter_x265 (bool): Whether to apply the x265 codec filter (default True).

    Returns:
        list: A list of dictionaries containing torrent information.
    """
    base_url = "https://thepiratebay10.xyz/search/"

    # Determine the codec filter string
    codec_filter = " x265" if filter_x265 else " h265" if filter_h265 else ""

    # Append a type-specific suffix to the search query
    if type == "movie":
        type_suffix = "/1/99/201"
    elif type == "tv":
        type_suffix = "/1/99/205"
    else:
        type_suffix = ""

    # Construct the complete search query and URL
    search_query = f"{query}{codec_filter}{type_suffix}"
    url = base_url + requests.utils.quote(search_query)

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/115.0 Safari/537.36")
    }
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return []

    # Parse HTML content with BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", id="searchResult")
    results = []

    if not table:
        print("No table found")
        return []

    # Iterate over each row in the results table
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        title_tag = cells[1].find("a", href=True, title=True)
        magnet_link = row.find("a", title="Download this torrent using magnet")
        size_cell = cells[4]

        if title_tag and magnet_link and size_cell:
            title_text = title_tag.get_text(strip=True)
            magnet = magnet_link['href']
            size_text = size_cell.get_text(strip=True)
            results.append({"title": title_text, "magnet": magnet, "size": size_text})

    print(f"Found {len(results)} torrents.")
    return results


def add_torrent_to_qbittorrent(magnet_link, media_type):
    """
    Add a torrent to qBittorrent based on the provided media type.
    """
    qb_url = "http://plex:8080"
    add_url = f"{qb_url}/api/v2/torrents/add"

    # Select the save path according to media type
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
    """
    A wrapper function to add a torrent to qBittorrent.
    """
    return add_torrent_to_qbittorrent(magnet_link, media_type)


@app.route("/process/<type>/<title>/", defaults={"season": None, "episode": None})
@app.route("/process/<type>/<title>/<season>/", defaults={"episode": None})
@app.route("/process/<type>/<title>/<season>/<episode>")
def process_title(type, title, season, episode):
    """
    Process the title search by constructing the query, performing sequential
    searches with x265, h265, and no codec filters, and consolidating results.
    """
    # Build the search query based on media type and optional season/episode info
    if type == "tv" and season and not episode:
        season_str = f"S{int(season):02d}"
        search_query = f"{title} {season_str}"
    elif type == "tv" and season and episode:
        season_episode_str = f"S{int(season):02d}E{int(episode):02d}"
        search_query = f"{title} {season_episode_str}"
    else:
        search_query = title

    collected_results = []
    seen_titles = set()

    def append_unique(results):
        """
        Append new results to the collected list ensuring unique titles.
        """
        for item in results:
            if item['title'] not in seen_titles:
                collected_results.append(item)
                seen_titles.add(item['title'])

    # Step 1: Search using the x265 codec
    x265_results = search_piratebay(search_query, type=type, filter_h265=False, filter_x265=True)
    append_unique(x265_results)

    # Step 2: If less than 10 results, search using the h265 codec and append new items
    if len(collected_results) < 10:
        h265_results = search_piratebay(search_query, type=type, filter_h265=True, filter_x265=False)
        append_unique(h265_results)

    # Step 3: If still less than 10 results, perform a search without codec filtering
    if len(collected_results) < 10:
        no_filter_results = search_piratebay(search_query, type=type, filter_h265=False, filter_x265=False)
        append_unique(no_filter_results)

    # Limit to a maximum of 10 results
    final_results = collected_results[:10]

    if not final_results:
        return render_template("message.html", title="No Results Found",
                               message="No torrents found for your search."), 404

    # Save the results and media type in session for later use
    session['results'] = final_results
    session['media_type'] = type

    return render_template("results.html", results=final_results)


@app.route("/select", methods=["POST"])
def select_torrent():
    """
    Process the user's torrent selection and add the selected torrent to qBittorrent.
    """
    selected_index = request.form.get("selected")
    passkey = request.form.get("passkey", "")

    # Validate passkey
    if passkey not in ["krummensam", "graceplex"]:
        return render_template("message.html", title="Unauthorized",
                               message="Incorrect password. Access denied."), 403

    # Validate selection input
    if selected_index is None:
        return render_template("message.html", title="Selection Error",
                               message="No selection was made."), 400

    try:
        selected_index = int(selected_index)
    except ValueError:
        return render_template("message.html", title="Invalid Selection",
                               message="Your selection is not valid."), 400

    results = session.get("results")
    media_type = session.get("media_type", "movie")

    if not results or selected_index >= len(results):
        return render_template("message.html", title="Selection Out of Range",
                               message="Your selection is out of range."), 400

    selected_torrent = results[selected_index]

    # Attempt to add the selected torrent to qBittorrent
    if add_to_qb(selected_torrent["magnet"], media_type):
        return render_template("message.html", title="Success",
                               message="Torrent successfully added to qBittorrent!")
    else:
        return render_template("message.html", title="Failure",
                               message="Failed to add torrent to qBittorrent."), 500


if __name__ == "__main__":
    app.run(debug=True, port=8000, host='0.0.0.0')
