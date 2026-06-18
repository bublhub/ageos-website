const ENTERPRISE_EMAIL = "daniel@ageos-labs.com";

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const text = button.getAttribute("data-copy");

    try {
      await navigator.clipboard.writeText(text);
      const previousLabel = button.textContent;
      button.textContent = "Copied";
      button.classList.add("is-copied");

      window.setTimeout(() => {
        button.textContent = previousLabel;
        button.classList.remove("is-copied");
      }, 1400);
    } catch {
      button.textContent = "Select text";
    }
  });
});

const demoVideo = document.querySelector("#demo-video");

if (demoVideo) {
  demoVideo.addEventListener("canplay", () => {
    demoVideo.closest(".demo-card")?.classList.add("has-video");
  });
}

const enterpriseForm = document.querySelector("#enterprise-form");

enterpriseForm?.addEventListener("submit", (event) => {
  event.preventDefault();

  const formData = new FormData(enterpriseForm);
  const name = formData.get("name")?.toString().trim() || "Unknown";
  const email = formData.get("email")?.toString().trim() || "Unknown";
  const company = formData.get("company")?.toString().trim() || "Unknown";
  const message = formData.get("message")?.toString().trim() || "";

  const subject = encodeURIComponent(`AgeOS enterprise inquiry from ${company}`);
  const body = encodeURIComponent(
    [
      `Name: ${name}`,
      `Email: ${email}`,
      `Company: ${company}`,
      "",
      "What they want to run locally:",
      message,
    ].join("\n"),
  );

  window.location.href = `mailto:${ENTERPRISE_EMAIL}?subject=${subject}&body=${body}`;
});
