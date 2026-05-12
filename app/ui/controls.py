import streamlit as st

from ui.uploader import render_background_uploader


def render_effect_controls(col3):

    effect_label = st.selectbox(
        "Select Effect",
        ["None", "Blur Background", "White Background", "Replace Background"],
    )

    effect_map = {
        "None": "none",
        "Blur Background": "blur",
        "White Background": "white",
        "Replace Background": "replace",
    }

    effect = effect_map[effect_label]

    blur_strength = 51
    bg_image = None
    uploaded_bg = None

    # Blurr settings
    if effect == "blur":

        blur_option = st.selectbox("Blur Strength", ["Light", "Medium", "Strong"])

        blur_map = {"Light": 21, "Medium": 51, "Strong": 101}

        blur_strength = blur_map[blur_option]

    # Bg image settings
    if effect == "replace":

        uploaded_bg, bg_image = render_background_uploader()

        # Preview image
        if bg_image is not None:

            with col3:

                st.markdown("Uploaded Image")

                st.image(bg_image, caption=uploaded_bg.name, use_container_width=True)

    return (effect, blur_strength, bg_image,uploaded_bg)
