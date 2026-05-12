import streamlit as st


def show_uploaded_video_preview(uploaded_file, file_path, col1):

    with col1:

        st.markdown("Uploaded Video")

        st.video(uploaded_file, width=800)

        st.success(f"File saved: {file_path.name}")


def show_video_comparison(uploaded_file, video_path, col1, col2):

    with col1:

        st.subheader("Original Video")

        st.video(uploaded_file)

    with col2:

        st.subheader("Processed Video")

        st.video(str(video_path))


def show_background_preview(bg_image, uploaded_bg, col3):

    if bg_image is not None and uploaded_bg:

        with col3:

            st.markdown("Uploaded Image")

            st.image(bg_image, caption=uploaded_bg.name, use_container_width=True)


def show_download_button(video_path):

    if video_path:

        with open(video_path, "rb") as file:

            st.download_button(
                label="Download Video",
                data=file,
                file_name="processed_video.mp4",
                mime="video/mp4",
            )
