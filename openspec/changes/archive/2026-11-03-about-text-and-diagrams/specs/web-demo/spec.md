## MODIFIED Requirements

### Requirement: Links in the description are safe
Links in the About text SHALL open in a new tab without giving the new page access to this one, and the About tab MUST NOT load scripts, images or fonts from another site. The only images the About tab shows are the project's own diagrams, served from this site.

#### Scenario: A link opens safely
- **WHEN** the About tab contains a link to another address
- **THEN** the link opens in a new tab with `noopener` and `noreferrer`, and the tab makes no request to another site

#### Scenario: Only this site's diagrams
- **WHEN** the About tab is opened
- **THEN** every image on it has an address on this site and ends in `.svg`, and no other image is rendered

### Requirement: The About tab tells the project's story
The About text SHALL state, in plain words, that the disease is fictional and often overlooked, that caught early it is highly treatable, and that missed it becomes a degenerative neurological disease. It SHALL describe the pathway of screen, confirm and treat, as a diagram and in words, say this project is the first stage, and name both costs of delay: the patient's time to diagnosis and the institution's rework and denials.

#### Scenario: The story sections are present
- **WHEN** the About tab is opened
- **THEN** its text contains the disease course, the three-stage pathway with this project marked as stage one, and a statement of the patient and institution costs of delay, each under a heading

#### Scenario: The pathway is a graphic
- **WHEN** the pathway section is read
- **THEN** it holds an image, not text drawn with characters, and the image names the three stages, marks this project as stage one and shows both costs

#### Scenario: The story stays fictional
- **WHEN** the story sections of the About text are searched for treatment names, doses, any figure, and dollar or days-saved amounts
- **THEN** none is found

## ADDED Requirements

### Requirement: The About text shows its diagrams
A line of the About text that holds only an image of an `.svg` file in the repository's `web/public` folder SHALL be shown as a figure whose image is that file served from this site, so the same line shows the image in the repository README. The About text SHALL have a diagram of the pathway and a diagram of how a request packet is made. Each SHALL have alt text that describes it in full, SHALL say nothing the text does not, and MUST NOT state an accuracy figure, a cost amount or a verdict word. The renderer MUST NOT show any other image.

#### Scenario: Both diagrams load
- **WHEN** the About tab is opened
- **THEN** two figures are shown, each image loads from this site and each has alt text

#### Scenario: The path is not shown
- **WHEN** the About tab is read
- **THEN** it contains no repository file path, and the repository README, which holds the same lines, shows the images

#### Scenario: Other images are refused
- **WHEN** the About text contains an image that points to another address or to another folder
- **THEN** it is not rendered as an image and loads nothing

### Requirement: The About text describes both scenarios
The About text SHALL describe the review queue, with the request packet and the supervisor's decision, and Estimate a risk, with its live dial that calls no language model and its route to the assistant. It SHALL say the assistant has no conversation memory and that the free-text box is inside Estimate a risk. It SHALL say the packet's parts are labelled with what produced them, that the risk estimate is context only and decides no criterion, and that nothing is sent anywhere.

#### Scenario: Both scenarios are named
- **WHEN** the About text is read
- **THEN** it names the review queue and Estimate a risk and says what a visitor does in each

#### Scenario: No stale description
- **WHEN** the About text is searched for a description of the demo as only a chat interface
- **THEN** none is found
