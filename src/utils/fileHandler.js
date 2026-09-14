const fs = require('fs').promises;
const path = require('path');

/**
 * Delete a file from the uploads directory
 */
const deleteFile = async (filePath) => {
  try {
    await fs.unlink(filePath);
    console.log(`File deleted: ${filePath}`);
  } catch (error) {
    console.error(`Error deleting file: ${error.message}`);
  }
};

/**
 * Read file as buffer
 */
const readFileAsBuffer = async (filePath) => {
  try {
    return await fs.readFile(filePath);
  } catch (error) {
    console.error(`Error reading file: ${error.message}`);
    throw error;
  }
};

module.exports = {
  deleteFile,
  readFileAsBuffer,
};
